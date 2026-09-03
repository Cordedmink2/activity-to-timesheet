<#
.SYNOPSIS
  The calendar adapter for classic Outlook: one day of the default calendar, printed in
  the contract calendar_day.py reads.

.DESCRIPTION
  Run by calendar_day.py when TIMESHEET_OUTLOOK_CALENDAR is true, as

    powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File outlook_calendar.ps1 YYYY-MM-DD

  It opens classic Outlook's COM object model (starting Outlook in the background when it
  is not running, and never closing it), reads the DEFAULT calendar only - shared and
  delegate calendars are other folders and are not looked at - expands a recurring calendar
  event into its instances around the requested day, and prints one UTF-8 JSON document:

    {"events": [{"id", "subject", "start", "end", "show_as", "response",
                 "all_day", "cancelled", "attendees"}, ...]}

  Basic fields only: no body, no location. Instants are UTC ("...Z"); the wrapper decides
  which day and clock that is in the configured zone, so this script never has to agree
  with it about time zones. The window read is the requested day plus a day either side
  for the same reason: the machine's day and the configured zone's day need not be the
  same one, and the wrapper keeps only events that start on its day.

  Every field is present on every event. An appointment the user wrote themselves
  (olNonMeeting) has no response to give and is reported as "organizer" - the user
  authored it. An instance of a recurring meeting reports the series master's EntryID,
  so its id carries the occurrence's start as well.

  Failure is one line on stderr and a non-zero exit: 2 for a bad argument, 1 for a
  calendar that cannot be read - no classic Outlook, no default calendar, a COM call
  refused. The wrapper carries the first line of that to the user.

  Parses under Windows PowerShell 5.1, which is the shell a stock Windows box has and the
  one the wrapper runs it in. The functions are kept apart from the main body so a test
  can dot-source this file and drive them without an Outlook.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Date = ""
)

$ErrorActionPreference = "Stop"

# --- Outlook's enumerations, by number ------------------------------------------------
# The object model hands back integers; the interop assembly that names them is not
# reliably loaded in a bare PowerShell. Read out of Microsoft.Office.Interop.Outlook 15.0
# on 2026-09-04; a value outside these tables is refused by name, never guessed at.
$OlBusyStatus = @{
    0 = "free"; 1 = "tentative"; 2 = "busy"; 3 = "out_of_office"; 4 = "working_elsewhere"
}
$OlResponseStatus = @{
    0 = "none"; 1 = "organizer"; 2 = "tentative"; 3 = "accepted"; 4 = "declined"; 5 = "not_responded"
}
$OlMeetingStatus = @{ 0 = $true; 1 = $true; 3 = $true; 5 = $true; 7 = $true }   # the values that exist
$olNonMeeting = 0                     # OlMeetingStatus: an appointment, not a meeting
$olMeetingCanceled = 5                # a meeting the user organised and cancelled
$olMeetingReceivedAndCanceled = 7     # a meeting the user received that was cancelled
$olResource = 3                       # OlMeetingRecipientType: a room, not a person
$olFolderCalendar = 9                 # OlDefaultFolders

function Fail([string]$Reason, [int]$Code = 1) {
    # One line, first, because the wrapper reads the first non-blank line as the reason; as
    # UTF-8 bytes, like stdout, because a reason may quote a subject.
    $line = ($Reason -replace "\r?\n", " ") + "`n"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($line)     # GetBytes never writes a BOM
    $stderr = [Console]::OpenStandardError()
    $stderr.Write($bytes, 0, $bytes.Length)
    $stderr.Flush()
    exit $Code
}

function ConvertTo-Instant([datetime]$Utc) {
    # Outlook's StartUTC/EndUTC are UTC values of Kind Unspecified; said so, then printed
    # as the Z form the wrapper reads. Outlook keeps minutes, so no fraction.
    return [DateTime]::SpecifyKind($Utc, [DateTimeKind]::Utc).ToString("yyyy-MM-dd'T'HH:mm:ss'Z'")
}

function ConvertTo-CalendarEvent($Item) {
    <#
      One AppointmentItem - or anything with its members - as the contract's event.
      An ordered hashtable so the document reads in the contract's order.
    #>
    $subject = ([string]$Item.Subject).Trim()
    $start = ConvertTo-Instant $Item.StartUTC
    $end = ConvertTo-Instant $Item.EndUTC

    $busy = [int]$Item.BusyStatus
    if (-not $OlBusyStatus.ContainsKey($busy)) {
        Fail "Outlook reported a show-as of $busy for '$subject', which this adapter does not know"
    }
    $meeting = [int]$Item.MeetingStatus
    if (-not $OlMeetingStatus.ContainsKey($meeting)) {
        Fail "Outlook reported a meeting status of $meeting for '$subject', which this adapter does not know"
    }
    $responded = [int]$Item.ResponseStatus
    if ($meeting -eq $olNonMeeting) {
        # An appointment the user wrote: Outlook says olResponseNone or olResponseOrganized
        # depending on how it was made, and neither is an answer to an invitation. The user
        # authored it, and the wrapper drops "none".
        $response = "organizer"
    } elseif ($OlResponseStatus.ContainsKey($responded)) {
        $response = $OlResponseStatus[$responded]
    } else {
        Fail "Outlook reported a response of $responded for '$subject', which this adapter does not know"
    }

    # Instances of a recurring meeting all report the series master's EntryID, so an
    # instance's id carries its own start; a one-off keeps the bare id, which the
    # drill-down can reopen directly.
    $id = [string]$Item.EntryID
    if ([bool]$Item.IsRecurring) { $id = "$id/$start" }

    # People, not rooms: a resource is where the meeting was, and would otherwise reach the
    # rules as an attendee name.
    $attendees = New-Object System.Collections.ArrayList
    foreach ($recipient in $Item.Recipients) {
        if ($null -eq $recipient) { continue }
        if ([int]$recipient.Type -eq $olResource) { continue }
        $name = ([string]$recipient.Name).Trim()
        if ($name) { [void]$attendees.Add($name) }
    }

    return [ordered]@{
        id        = $id
        subject   = $subject
        start     = $start
        end       = $end
        show_as   = $OlBusyStatus[$busy]
        response  = $response
        all_day   = [bool]$Item.AllDayEvent
        cancelled = ($meeting -eq $olMeetingCanceled -or $meeting -eq $olMeetingReceivedAndCanceled)
        attendees = [string[]]$attendees.ToArray()
    }
}

function Read-CalendarDay([datetime]$Day) {
    <#
      Every calendar event in the default calendar touching the three days around $Day,
      recurring ones expanded into their instances, as contract events.
    #>
    try {
        $outlook = New-Object -ComObject Outlook.Application
    } catch {
        $said = $_.Exception.Message
        if ($said -match "80040154") {
            Fail "classic Outlook is not installed on this machine (its object model, Outlook.Application, is not registered), so the calendar cannot be read"
        }
        Fail "classic Outlook could not be started, so the calendar cannot be read: $said"
    }
    try {
        $namespace = $outlook.GetNamespace("MAPI")
        $calendar = $namespace.GetDefaultFolder($olFolderCalendar)
    } catch {
        Fail "classic Outlook has no default calendar to read: $($_.Exception.Message)"
    }

    # The documented order: sort, then include recurrences, then a date-bounded Restrict.
    # Unbounded, IncludeRecurrences enumerates a series forever; both [Start] and [End]
    # bound it here. Dates in the current culture's short form, which is what the Jet
    # filter parses.
    $from = $Day.Date.AddDays(-1)
    $to = $Day.Date.AddDays(2)
    try {
        $items = $calendar.Items
        $items.Sort("[Start]")
        $items.IncludeRecurrences = $true
        $filter = "[Start] < '" + $to.ToString("g") + "' AND [End] > '" + $from.ToString("g") + "'"
        $found = $items.Restrict($filter)
    } catch {
        Fail "classic Outlook refused to list the calendar: $($_.Exception.Message)"
    }

    $events = New-Object System.Collections.ArrayList
    $item = $found.GetFirst()
    while ($null -ne $item) {
        [void]$events.Add((ConvertTo-CalendarEvent $item))
        $item = $found.GetNext()
    }
    return $events.ToArray()
}

function Write-CalendarDay($Events) {
    <#
      The one document, as UTF-8 bytes straight to stdout. Windows PowerShell writes a
      redirected stdout in the console code page, which is not UTF-8 and would mangle a
      macron; the wrapper reads UTF-8 by contract. The [object[]] cast keeps one event an
      array of one, which PowerShell would otherwise unwrap.
    #>
    # `Where-Object` first: a function returning an empty array hands back $null, which
    # `@()` would wrap as one null event, and the wrapper refuses "event 0 is not an object".
    $document = [ordered]@{ events = [object[]]@(@($Events) | Where-Object { $null -ne $_ }) }
    $json = ConvertTo-Json -InputObject $document -Depth 6
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)     # GetBytes never writes a BOM
    $stdout = [Console]::OpenStandardOutput()
    $stdout.Write($bytes, 0, $bytes.Length)
    $stdout.Flush()
}

# --- The command -----------------------------------------------------------------------
# Skipped when this file is dot-sourced, which is how the tests reach the functions above.
if ($MyInvocation.InvocationName -ne ".") {
    if (-not $Date) {
        Fail "usage: outlook_calendar.ps1 YYYY-MM-DD" 2
    }
    try {
        $day = [datetime]::ParseExact($Date, "yyyy-MM-dd", [System.Globalization.CultureInfo]::InvariantCulture)
    } catch {
        Fail "bad date '$Date', expected YYYY-MM-DD" 2
    }
    if ($PSVersionTable.PSEdition -eq "Core" -and -not $IsWindows) {
        Fail "classic Outlook's object model exists on Windows alone, so the calendar cannot be read here"
    }
    try {
        Write-CalendarDay (Read-CalendarDay $day)
    } catch {
        Fail "the calendar could not be read: $($_.Exception.Message)"
    }
    exit 0
}
