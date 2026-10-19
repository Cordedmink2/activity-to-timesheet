"""One module per kind of work-item system. An adapter module defines:

    NAME            the value of `- Adapter:` that selects it (the file's own name)
    REQUIRED        the `.context.md` labels it cannot run without
    LEGACY          {old setting key: the label that replaced it}, for a run that finds
                    the shape this adapter used before #37
    fetch(facts, run, which) -> (catalog text, [warning, ...])

`run` and `which` are `subprocess.run` / `shutil.which`, passed in so a test never starts a
process. The seam in `source.py` finds adapters by listing this directory and names none.
"""
