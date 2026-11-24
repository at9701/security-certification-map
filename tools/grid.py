import re,sys,json
src=open(sys.argv[1],encoding='utf-8').read()
# spans from css
spans={}
for m in re.finditer(r'\.([\w-]+)\s*\{([^}]*)\}',src):
    s=re.search(r'grid-column:\s*span\s*(\d+)',m.group(2))
    spans[m.group(1)]=int(s.group(1)) if s else 1
a=src.index('<div class="certcontainer">'); 
body=src[a:]
tok=re.compile(r'<div class="{0,2}(spacer\d*|skilllevelitem)"[^>]*>.*?</div>|<a class="([\w-]+)"[^>]*?>(.*?)</a>|<!--(.*?)-->',re.S)
NC=47
zones=[(1,1,'lvl'),(2,4,'net'),(5,5,'|'),(6,6,'iam'),(7,7,'|'),(8,11,'cloud'),(12,12,'nix'),(13,13,'ics'),(14,14,'eng'),(15,15,'|'),(16,17,'asset'),(18,18,'|'),(19,27,'mgmt'),(28,28,'|'),(29,31,'test'),(32,32,'|'),(33,33,'sw'),(34,34,'|'),(35,36,'blue'),(37,38,'forens'),(39,40,'ih'),(41,45,'pent'),(46,47,'expl')]
def zone(c):
    for lo,hi,n in zones:
        if lo<=c<=hi: return n
row=1;col=1;cells=[]
end=body.index('</div>\n',0)
pos=len('<div class="certcontainer">')
for m in tok.finditer(body,pos):
    if m.group(4) is not None: continue
    # stop when leaving container: detect by a closing div between tokens
    between=body[pos:m.start()]
    if '</div>' in between: break
    cls=m.group(1) or m.group(2)
    sp=spans.get(cls,1)
    if cls=='skilllevelitem': sp=1
    if col+sp-1>NC: row+=1;col=1
    label=re.sub(r'<.*?>','',m.group(3) or '').strip()
    cells.append(dict(row=row,col=col,span=sp,cls=cls,label=label,off=a+m.start(),end=a+m.end()))
    col+=sp
    if col>NC: row+=1;col=1
    pos=m.end()
json.dump(cells,open(sys.argv[2] if len(sys.argv)>2 else '/dev/null','w'))
print('rows',row,'cells',len(cells))
mode='map'
import collections
byrow=collections.defaultdict(list)
for c in cells: byrow[c['row']].append(c)
for r in sorted(byrow):
    line=[]
    for c in byrow[r]:
        if c['cls'].startswith('spacer'):
            if c['span']==1 and zone(c['col'])!='|': line.append(f"[{c['col']}{zone(c['col'])}]")
            elif c['span']>1: line.append(f"<{c['col']}-{c['col']+c['span']-1}>")
        else: line.append(f"{c['label']}@{c['col']}" + (f"x{c['span']}" if c['span']>1 else ''))
    tot=sum(c['span'] for c in byrow[r])
    print(r,tot,' '.join(line))
