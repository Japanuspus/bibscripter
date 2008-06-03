import bibScripter
def printRef(entry):
    "Print entry key and std. reference"
    print '%-40s: %s'%(entry.getReference(),entry.key.val)

bibScripter.runEntries(printRef)
