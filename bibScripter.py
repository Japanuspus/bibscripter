# bibScripter.py v0.0 
#
#    This file is part of bibScripter.
#
#    bibScripter is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    bibScripter is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with bibScripter.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2008, Janus H. Wesenberg
# For updates: http://code.google.com/p/bibscripter/

import re,sys
import os.path,shutil
import logging

#Syntax assumptions (see also, http://www.bibtex.org/Format/)
# - all entries have @<typenane>{ on start of new line
#<typename>: comment,string,preamble are special


class HeldString(object):
    """ 
    Represents a string with some wrapping to allow minimal impact editing.
    - str() returns "<head>"+"<val>"+"<tail>"
    - val sets/gets value
    - fullStr() returns full wrapped string
    - if a new value is set, wrapping is kept
    - otherwise fullString() is as original
    """
    def  __init__(self,inStr='',headTail=None,valPart=None):
        " val/full is either inStr[valPart]/inStr or inStr/head+inStr+tail"
        if headTail==None:
            self.str=inStr;
            if valPart!=None:
                self.vStart=valPart[0]
                self.vEnd=valPart[1]
            else:
                self.vStart=0
                self.vEnd=len(inStr)
        else:
            if valPart!=None:
                logging.warning("Bug: Ignoring valPart since headTail specified. inStr=%s,ht=%s,vp=%s",
                                inStr,str(headTail),str(valPart))
            self.str=headTail[0]+inStr+headTail[1]
            self.vStart=len(headTail[0])
            self.vEnd=self.vStart+len(inStr)

    def __str__(self):
        return '>>%s<>%s<>%s<'%(self.head(),self.getVal(),self.tail())
    def fullString(self):
        "Wrapped string"
        return self.str
    def head(self):
        return self.str[0:self.vStart]
    def tail(self):
        return self.str[self.vEnd:]

    def getVal(self):
        "Value of string, without wrapping"
        return self.str[self.vStart:self.vEnd]
    def setVal(self,val):
        self.str=self.head()+val+self.tail()
        self.vEnd=self.vStart+len(val)
    val=property(getVal,setVal)

class BibField:
    """
    A single field in a BibEntry.
    key and wall must implement fullString.
    Default form would be <key.val> = <val.val>,\\n
    """
    def __init__(self,key,val):
       self.key=key
       self.val=val
       if val==None or key==None:
           logging.warning('Illegal init of BibField: %s,%s',key,val)

    def __str__(self):
        return '\t%-10s: %s'%(self.key.val,self.val.val.replace('\n','').strip())

    def fullString(self):
        return self.key.fullString()+self.val.fullString()
        
class BibSpecialEntry:
    "Special entries (comments, etc)"
    def __init__(self,type,val):
        "All members must implemnt the fullString method"
        self.val=val
        self.type=type

    def __str__(self):
        return "@%s\n%s"%(self.type.val,self.val.val.replace('\n','').strip())
        
    def fullString(self):
        return ''.join([i.fullString() for i in [self.type,self.val]])

class BibEntry:
    "A bibtex entry. Holds full string of entry + trailing space."

    def __init__(self,type,key,fields):
        "All members must implemnt the fullString method"
        self.fields=fields
        self.type=type
        self.key=key
        
    def __str__(self):
        return(('@%s, %s\n'%(self.type.val,self.key.val))+
               '\n'.join([str(f) for f in self.getFields()]))
    def fullString(self):
        return ''.join([i.fullString() for i in ([self.type,self.key]+self.fields)])
    def getFields(self):
        return filter(lambda f:isinstance(f,BibField),self.fields)
    def getFieldsMap(self):
        return dict([(field.key.val,field) for field in self.getFields()])
    def getFieldsValueMap(self):
        "Return a map to field values with braces stripped"
        try:
            return dict([(field.key.val,stripBraces(field.val.val)) for field in self.getFields()])
        except:
            print '***************************'
            print self.type
            print self.key
            for f in self.fields:
                print f.__class__
                print f
            raise

    def getReference(self):
        fields=self.getFieldsValueMap()
        if self.type.val.lower()=='article':
            if fields.has_key('journal'):
                return '%s %s, %s (%s)'%(
                    fields.get('journal'),
                    fields.get('volume',''),
                    fields.get('pages','').split('-',1)[0],
                    fields.get('year','')
                    )
            elif fields.has_key('eprint'):
                return fields.get('eprint')
        #Fallback
        return self.key.val

class BibFile:
    """ 
A bibfile with parser.
All entries are assumed to have @ on start of line.
Basic design idea: all text is attached to an entry.
This could imply a typeless entry at first position in entrylist.
    """
    specialTypes=['string','comment','preamble']
    def __init__(self,bibFileName=None):
        self.bibFileName=bibFileName
        self.entries=[]
        if bibFileName!=None:
            self.parse(bibFileName)

    def parse(self,bibFileName):
        self.bibFileName=bibFileName
        self.entries=[]
        parser=BibEntryParser()
        infile=open(self.bibFileName,'r')
        entryBuf=''
        #Block parser: look for lines starting with @
        for line in infile:
            if line.startswith('@'):
                if entryBuf<>'':
                    self.entries.append(parser.parseEntry(entryBuf))
                    entryBuf=line
            else:
                entryBuf+=line
        infile.close()
        if entryBuf<>'':
            self.entries.append(parser.parseEntry(entryBuf))

    def writeFile(self,bibFileName=None):
        fnam=bibFileName
        if fnam==None:
            fnam=self.bibFileName
            if os.path.isfile(fnam):
                shutil.copy(fnam,fnam+'.bak')
        ofile=open(fnam,'w')
        for entry in self.entries:
            ofile.write(entry.fullString())
        ofile.close()

    def getEntries(self):
        "Return only proper entries. Access .entries directly for gunk"
        return filter(lambda e:isinstance(e,BibEntry),self.entries)
        
    def getEntriesMap():
        entriesMap=dict()
        for entry in self.entries:
            if not isinstance(entry,BibEntry):
                continue
            if entry.key.val!='':
                if entriesMap.has_key(entry.key.val):
                    logging.warning("Duplicate key: %s",entry.key.val)
                entriesMap[entry.key.val]=entry
            else:
                logging.warning("Missing key:\n %s ",str(entry))
        return entriesMap

class BibFileSubset:
    "A selection of entries, specified in terms of bibtexkeys"
    def __init__(self,bibFile):
        self.bibFile=bibFile
        self.keySet=set(self.bibFile.entriesMap.keys())

class BibEntryParser:
    """
A hand-coded recursive descent parser for bib-file entries.

<entry>: @<entrytypeLitt>{[<entryykeyLitt>],<attrlist>[,]}
<attrlist>: <attrpair>, <attrlist> | <attpair>
<attrpair>: <attrkeyLitt> = <attrval>
<attrval> : {<block>} | <stringlist>
<stringlist> : <string> # <stringlist> | <string>
<string> : "<block>" | <defstringLitt> 
<block> : <- nesting unescaped }{ ->

Fields holds a list of objects so that concatenate([str(o) for o in fields])
should be = the initial bibString.
    """

    def __init__(self):
        self.pos=0
        self.str=None
        self.fields=[]

    def makeHeld(self,full,val=None):
        "Make a held string from buffer"
        if val==None:
            return HeldString(self.str[full[0]:full[1]])
        else:
            return HeldString(self.str[full[0]:full[1]],
                       valPart=(val[0]-full[0],val[1]-full[1]))
                       
    reTypeKey=re.compile('@(\w*){([^,}\s]*),',re.M)
    reType=re.compile('@(\w*){')
    def parseEntry(self,bibEntryStr):
        self.pos=0 #always: first field not yet included in entry structure
        self.str=bibEntryStr
        self.fields=[]

        m=BibEntryParser.reTypeKey.match(self.str)
        if m==None or m.group(1).lower() in BibFile.specialTypes:
            #Special entry -- maybe just gunk string
            m=BibEntryParser.reType.match(self.str)
            if m<>None:
                return BibSpecialEntry(type=self.makeHeld((0,m.end()),m.span(1)),
                                       val=HeldString(self.str[m.end():]))
            return HeldString(self.str)
        else:
            #Full normal entry with type and key
            type=self.makeHeld((0,         m.start(2)),m.span(1))
            key =self.makeHeld((m.start(2),m.end()   ),m.span(2))
            self.pos=m.end()
            try:
                self.parseFields()
            except AttributeError:
                logging.warning("Unable to parse entry %s, including unparsed version",m.group(2))
                logging.info("""
*** Successfully parsed part: *** 
%s 
*** Remainder: *** 
%s
*** Parser state ***
++%s
""",
                             self.str[0:self.pos],
                             self.str[self.pos:],
                             '\n ++'.join([str(s) for s in [type,key]+self.fields])
                             )
                raise
                return BibEntry(type=type,key=key,fields=[HeldString(self.str[m.end():])])
            else:
                return BibEntry(type=type,key=key,fields=self.fields)

    reFieldStart=re.compile('\w|}',re.M)
    reVoid=re.compile('\S',re.M)
    def parseFields(self):
        """
        <attrlist>: <attrpair>, <attrlist> | <attpair>
        <attrpair>: <attrkeyLitt> = <attrval>
        """
        while True:
            # Look for \w or }
            m=BibEntryParser.reFieldStart.search(self.str,self.pos)
            # Let exception handle None 
            if m.group()=='}':
                #End of this entry.
                #Check that rest is only whitespace:
                m2=BibEntryParser.reVoid.search(self.str,m.end())
                if m2!=None:
                    logging.warning("Parsing problems. Follwing found on tail of entry:\n***%s***",
                                    self.str[m.end():])
                    print map(ord,self.str[m.end():])
                self.fields.append(HeldString(self.str[self.pos:]))
                break
            else:
                #another field proper
                self.fields.append(self.parseField())

    reFieldKey=re.compile('\s*(\w+)\s*=\s*',re.M)
    def parseField(self):
        m=BibEntryParser.reFieldKey.match(self.str,self.pos)
        key=self.makeHeld(m.span(),m.span(1))
        self.pos=m.end()
        if self.str[self.pos]=='{':
            val=self.parseBlockVal()
        else:
            val=self.parseStringList()
        return BibField(key=key,val=val)
            
    reStringList=re.compile('\S',re.M)
    reStringListDef=re.compile('\W')
    def parseStringList(self):
        sofGood=self.pos
        eofGood=self.pos
        while True:
            m=BibEntryParser.reStringList.search(self.str,self.pos)
            self.pos=m.start()
            s=self.str[self.pos]
            if s==',':
                self.pos=m.end()
                break
            elif s=='}':
                break
            if s=='"':
                self.parseBlock('"')
                eofGood=self.pos
            elif s=='#':
                self.pos=m.end()
            else:
                #defstring -- there must be termination
                m=BibEntryParser.reStringListDef.search(self.str,self.pos)
                self.pos=m.start()
                eofGood=self.pos
        return self.makeHeld((sofGood,self.pos),(sofGood,eofGood))

    reBlockVal=re.compile('[,}]',re.M)
    def parseBlockVal(self):
        sofBlock=self.pos
        self.parseBlock()
        #Find out if there is a ',' to include
        m=BibEntryParser.reBlockVal.search(self.str,self.pos)
        if m.group()==',':
            block=(sofBlock,self.pos)
            self.pos=m.end()
            return self.makeHeld((sofBlock,self.pos),block)
        else:
            #closing of entry goes as separate field
            return self.makeHeld((sofBlock,self.pos))

    reBlock=re.compile(r'({|}|")|(\\.)',re.M)
    dictLevel={'{':1,'"':0,'}':-1}
    def parseBlock(self):
        "Go to (incl) matching symbol at self.pos" 
        term=self.str[self.pos]
        if term=='{':
            term='}'
        level=0
        self.pos=self.pos+1
        while True:
            m=BibEntryParser.reBlock.search(self.str,self.pos)
            self.pos=m.end()
            if m.lastindex==1:  # not escaped character
                if level==0 and m.group(1)==term:
                    return
                level=level+BibEntryParser.dictLevel[m.group(1)]

def stripBraces(s):
    "Strip braces if present"
    if s[0]=='{' and s[-1]=='}':
        return s[1:-1]
    return s

# Just a bunch of functions
def testList(bibFile):
    for entry in bibFile.getEntries():
        print '%-20s: %s' % (entry.type.val, entry.key.val)

def setup(): 
    logging.basicConfig()
    logging.getLogger('').setLevel(logging.INFO)

def runFile(f):
    setup()
    bib=BibFile(sys.argv[1])
    f(bib)
    if len(sys.argv)>2:
        bib.writeFile(sys.argv[2])

def runEntries(f):
    setup()
    bib=BibFile(sys.argv[1])
    for entry in bib.getEntries():
        f(entry)
    if len(sys.argv)>2:
        bib.writeFile(sys.argv[2])

if __name__ =='__main__': 
    print """
bibScripter is a framework module for scripting bibTeX operations
minimal example (enter as bibScripterDemo.py):

import bibScripter
def printRef(entry):
    "Print entry key and std. reference"
    print '%-40s: %s'%(entry.getReference(),entry.key.val)

bibScripter.runEntries(printRef)

run with python bibScripterDemo.py <mybibfile> <outputfile>
with bibScripter.py in same directory or on path.
"""


