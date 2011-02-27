#! /usr/bin/python
# Written by Ryan http://photoblog.chezmojo.com
# I take no responsibility whatsoever for the use of this script.
# Feel free to edit and/or redistribute it, but please do give me credit.
#

"""
Requirements:
convert from http://www.imagemagick.org/script/index.php
dcraw from http://www.cybercom.net/~dcoffin/dcraw/
exiftool from http://www.sno.phy.queensu.ca/~phil/exiftool/
"""

import sys,os,time,threading,Queue,time,random
from getopt import gnu_getopt, GetoptError


TEAL="\033[36;1m"
RS="\033[0m"
CL="\033[2k"
YELLOW="\033[33;1m"
RED="\033[31;1m"
GREEN="\033[32;1m"
BLUE="\033[34;1m"
MAGENTA="\033[35;1m"

def ShowUsage():
    print '''
    -h --help: This list.
    -w --overwrite: Overwrite files that exist
    -o --out: Output directory (Default same as input)
    -e --ext: Type of file to convert (Default nef)
    -t --target: Target file type (Default jpg)
    -c --cpu: Number of cpus (Default 4)
    '''
    sys.exit(0)

class Opts():
    def __init__(self):
        self.numfiles = 0
        self.queue = Queue.Queue()
        self.bins = self.Find_Binaries(("dcraw","convert","exiftool"))
        if not self.bins:
            print RED,"***Can't find convert/dcraw/exiftool!",RS
            ShowUsage()
        try:
            opts, in_files = gnu_getopt(sys.argv[1:], "hwo:e:t:ac:", \
            ["help","overwrite","out","ext","target","auto","cpu"])
        except GetoptError:
            print "Invalid options"
            ShowUsage()
        #Defaults
        self.overwrite = False
        self.outdir = False
        self.ext = "nef"
        self.target = "jpg"
        self.auto = True
        self.cpus = 4
        #Args
        for opt,arg in opts:
            if opt in ('-h', '--help'):
                ShowUsage()
            if opt in ('-w','--overwrite'):
                self.overwrite = True
            if opt in ('-o','--out'):
                if not os.path.exists(arg):
                    os.mkdir(arg)
                if not os.path.isdir(arg):
                    print RED,arg,"isn't a directory!"
                    ShowUsage()
                self.outdir = str(arg)
                self.auto = False
            if opt in ('-e','--ext'):
                self.ext = str(arg)
            if opt in ('-t','--target'):
                self.target = str(arg.replace(".",""))
            if opt in ('-c-','--cpu'):
                self.cpus = int(arg)
        if not in_files:
            in_files = ['./']
        self.queuedir(in_files,self.ext)
        if self.queue.empty():
            print RED,"No input files!"
            sys.exit()
            
    def Find_Binaries(self,bins):
        paths = ["/bin/", "/usr/bin/", "/usr/local/bin/"]
        execs = {}
        for b in bins:      
            for p in paths:
                if os.access(os.path.join(p,b),os.X_OK):
                    execs[b]=os.path.join(p,b)
                    break
        if len(execs) != len(bins):
            return False
        else:
            return execs

    def queuedir(self,dirs,ext):
        if not len(ext) == 3:
            raise OSError, "Need three-character extension"
        for dir in dirs:
            if self.auto:
                for t in ('raw','jpeg'):
                    tdir = os.path.join(os.path.split(dir)[0],t)
                    if not os.path.exists(tdir):
                        os.mkdir(tdir)
                        print BLUE,"Making",tdir,RS
            if os.path.isdir(dir):
                d = os.listdir(dir)
            else:
                d = [dir]
            for f in d:
                if f.lower()[-3:] == ext.lower():
                    f = os.path.join(dir,f)
                    self.queue.put(f)
                    self.numfiles += 1
    def done(self):
        return float(self.numfiles - self.queue.qsize())

class Job(threading.Thread):
    def __init__(self,opts,alive,lock):
        threading.Thread.__init__(self)
        self.opts = opts
        self.alive = alive
        self.lock = lock
        self.queue = opts.queue
        self.__done = 0
        self.currentfile = ""	
    def run(self):
        self.alive.wait()
        while self.alive.isSet():
            try:
                if not self.lock.acquire(0):
                    time.sleep(0.25)
                    continue
                job = self.queue.get(True,1)
                self.queue.task_done()
                self.lock.release()
            except Queue.Empty:
                self.lock.release()
                break
            self.__done += self.__dojob(job)

    def __dojob(self, infile):
        self.currentfile = os.path.basename(infile)
        if self.opts.outdir:
            outdir = self.opts.outdir
        else:
            outdir = os.path.split(infile)[0]
        if self.opts.auto:
            outdir = os.path.join(outdir,'jpeg')
        outfile = os.path.join(outdir,\
                               os.path.basename(infile)[:-3]+self.opts.target)
        if os.path.exists(outfile):
            if not self.opts.overwrite:
                return 1
        if self.opts.auto:
            d,f = os.path.split(infile)
            os.rename(infile, os.path.join(d,'raw',f))
            infile = os.path.join(d,'raw',f)
        for c in (" ",":","(",")"):
            infile = infile.replace(c,'\\'+c)
            outfile = outfile.replace(c,'\\'+c)
        cmd1 = [self.opts.bins["dcraw"],"-T","-c","-h","-b","1.0","-H","2",infile]
        cmd2 = [self.opts.bins["convert"],"-scale","100%","-quality","92","-unsharp","0.3x3+1+0","-",outfile]
        #cmd1 = [self.opts.bins["dcraw"],"-T","-c","-b","0.7","-H","2","-w",infile]		
        #cmd2 = [self.opts.bins["convert"],"-scale","100%","-quality","90","-unsharp","0.3x3+1+0","-",outfile]
        cmd3 = [self.opts.bins["exiftool"],"-q","-overwrite_original_in_place","-TagsFromFile",infile,outfile]
        os.system(" ".join(cmd1)+"|"+" ".join(cmd2))
        os.system(" ".join(cmd3))
        return 1
    def getDone(self):
        return float(self.__done)

def moveup(count):
    r = []
    for i in range(count):
        r.append(CL)
        r.append("\033[1A\r")
    return "".join(r)

def prog(percent):
    """chars = ("@","#","$","%","&","*")
    rchr = chars[int(random.random() * len(chars))]
    sys.stdout.write(moveup(3))
    border = chr(26)
    for i in range(0,100,4):
        sys.stdout.write(MAGENTA+border)
    for i in range(7):
        sys.stdout.write(border)
    sys.stdout.write("\n"+RED+rchr)
    for i in range(0,100,4):
        if i <= percent:
            sys.stdout.write(TEAL+chr(24))
        else:
            sys.stdout.write(GREEN+chr(43))
    while len(str(percent)) < 3:
        percent = " "+str(percent)
    sys.stdout.write(YELLOW+str(percent)+"% "+MAGENTA+border+"\n")
    for i in range(0,100,4):
        sys.stdout.write(MAGENTA+border)
    for i in range(7):
        sys.stdout.write(border)
    sys.stdout.write("\n"+RS)
    sys.stdout.flush()"""

if __name__ == "__main__":
    opts = Opts()
    jobs = []
    alive = threading.Event()
    lock = threading.Lock()
    for i in range(opts.cpus):
        jobs.append(Job(opts,alive,lock))
        jobs[-1].start()
    alive.set()
    sys.stdout.write("\n\n\n")
    sys.stdout.flush()
    try:
        while threading.activeCount() > 1:
            done = 0.0
            for j in jobs:
                done += j.getDone()
                sys.stdout.write(BLUE+" "+j.currentfile+RS+"\r")
                sys.stdout.flush()
            percent = int(done/opts.numfiles*100)
            prog(percent)
            if percent > 100:
                raise KeyboardInterrupt
            time.sleep(0.15)
    except KeyboardInterrupt:
        print RED,"Dying"
        alive.clear()
    for j in jobs:
        j.join()
    print CL+BLUE+"Done!"+RS
    sys.exit()
