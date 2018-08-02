import errno
import io
import os
import re
import uuid
from shutil import copyfile

import mutagen
from PIL import Image, ImageOps
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.mp3 import EasyMP3
import traceback

MODE_1S=['general','editor','metadata','difficulty','colours']
MODE_2S=['events','hitobjects']

def isfloat(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def isint(value):
    try:
        int(value)
        return True
    except ValueError:
        return False

def filesafe(s):
    return "".join([c for c in s if c.isalpha() or c.isdigit() or c == ' ']).strip()

class OsuFile:
    def __init__(self,path=None):
        self.data={}
        self.path = path
        self.dir=os.path.dirname(self.path)
        with open(path, 'r', encoding='utf8') as f:
            self.raw = f.read()+'\n\n'
        self.declaration=self.raw.split('\n',1)[0]

        for m in re.finditer(r'\[(\w+)\]([\s\S]+?\n\n)',self.raw):
            name=m.group(1).strip()
            body=m.group(2)
            d={}
            l=[]
            mode= 1 if name.lower() in MODE_1S else (2 if name.lower() in MODE_2S else 0)
            for line in body.splitlines(keepends=False):
                if line.strip()!='':
                    if mode==1:
                        parts=line.split(':')
                        p2=parts[1].strip()
                        d[parts[0].strip()]=int(p2)if isint(p2) else (float(p2) if isfloat(p2) else p2)
                    elif mode==2:
                        l.append(line.strip())
                    else:
                        if ':' in line:
                            parts = line.split(':')
                            p2 = parts[1].strip()
                            d[parts[0].strip()] = int(p2)if isint(p2) else (float(p2) if isfloat(p2) else p2)
                        else:
                            l.append(line.strip())
            if len(d)>len(l):
                self.data[name]=d
            else:
                self.data[name]=l

    def __str__(self):
        return str(self.data)

    def title(self):
        return self.data['Metadata']['Title']

    def img(self):
        #should work for most
        for line in self.data['Events']:
            if line.startswith('0,0,"'):
                m=re.search(r'\"([^\"]+)\"',line)
                return os.path.join(self.dir,m.group(1))
        return None

    def audio(self):
        return os.path.join(self.dir,self.data['General']['AudioFilename'])

    def to_mp3(self,outDir=None,album="Osu"):
        if not self.audio().endswith('.mp3'): return False # non mp3 not supported
        if outDir is None: outDir='output'
        if not os.path.exists(outDir):
            try:
                os.makedirs(outDir)
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        out=os.path.join(outDir,filesafe(self.title())+'.mp3')
        copyfile(self.audio(),out)

        #basic editing
        try:
            audio=EasyID3(out)
            audio.delete()
        except ID3NoHeaderError:
            audio=mutagen.File(out,easy=True)
            audio.add_tags()
        try:
            audio['title']=self.data['Metadata']['TitleUnicode']
        except KeyError:
            audio['title']=self.data['Metadata']['Title']
        try:
            audio['artist']=self.data['Metadata']['ArtistUnicode']
        except KeyError:
            audio['artist']=self.data['Metadata']['Artist']
        audio['album']=album
        audio.save()

        #advanced editing
        audio = MP3(out,translate=True)
        try:
            with io.BytesIO() as output:
                with Image.open(self.img()) as img:
                    # img.thumbnail((512, 512), Image.ANTIALIAS)
                    # img=ImageOps.fit(img,(512,512),Image.ANTIALIAS)
                    img.save(output, 'PNG')
                imgdata = output.getvalue()
        except:
            with open(self.img(),'rb') as img:
                imgdata=img.read()

        audio.tags.add(APIC(
            encoding=3,
            mime='image/png',
            type=3,
            desc='Front cover',
            data=imgdata
        ))
        audio.save()


# if __name__ =='__main__':
#     songs_dir=os.path.join(os.getenv('LOCALAPPDATA'),'osu!','Songs')
#     if not os.path.isdir(songs_dir): songs_dir=input('Please enter osu Songs directory: ').strip().encode("ascii", errors="ignore").decode()
#     sdirs=[os.path.join(songs_dir, o) for o in os.listdir(songs_dir) if os.path.isdir(os.path.join(songs_dir,o))]
#     for sdir in sdirs:
#         file=None
#         try:
#             file=[os.path.join(sdir,o) for o in os.listdir(sdir) if o.endswith('.osu')][0]
#         except IndexError:
#             #no osu file detected in this dir
#             pass
#         if file is not None:
#             osu = OsuFile(file)
#             print(osu.title())
#             # if osu.title().lower()=='osu! tutorial'.lower():
#             print(osu.to_mp3())
#             # break

if __name__ =='__main__':
    songs_dir=os.path.join(os.getenv('LOCALAPPDATA'),'osu!','Songs')
    if not os.path.isdir(songs_dir): songs_dir=input('Please enter osu Songs directory: ').strip().encode("ascii", errors="ignore").decode()
    col_file=input('Please enter collections dump file path: ').strip().encode("ascii", errors="ignore").decode()
    maps=[]
    with open(col_file,'r') as cf:
        file=cf.read()
        for m in re.finditer(r'(.+?)\[',file):
            maps.append(m.group(1))

    sdirs=[os.path.join(songs_dir, o) for o in os.listdir(songs_dir) if os.path.isdir(os.path.join(songs_dir,o))]
    for sdir in sdirs:
        file=None
        try:
            file=[os.path.join(sdir,o) for o in os.listdir(sdir) if o.endswith('.osu')][0]
        except IndexError:
            #no osu file detected in this dir
            pass
        if file is not None:
            osu = OsuFile(file)
            if any([osu.title() == x.replace(osu.data['Metadata']['Artist']+' - ','').strip() for x in maps]):
                print(osu.title())
                # if osu.title().lower()=='osu! tutorial'.lower():
                try:
                    osu.to_mp3()
                except:
                    print("UNCAUGHT ERROR!!")
                    traceback.print_exc()
            # break