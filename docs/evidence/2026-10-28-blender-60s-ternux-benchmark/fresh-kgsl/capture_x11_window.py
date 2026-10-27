import ctypes, ctypes.util, struct, zlib, sys, json, subprocess
wid=int(sys.argv[1]); out=sys.argv[2]
geo=subprocess.check_output(['sh','-c',f'DISPLAY=:0 xdotool getwindowgeometry --shell {wid}'],text=True)
vals={line.split('=',1)[0]:int(line.split('=',1)[1]) for line in geo.splitlines() if '=' in line}
w,h=vals['WIDTH'],vals['HEIGHT']
class XImage(ctypes.Structure):
    _fields_=[('width',ctypes.c_int),('height',ctypes.c_int),('xoffset',ctypes.c_int),('format',ctypes.c_int),('data',ctypes.c_void_p),('byte_order',ctypes.c_int),('bitmap_unit',ctypes.c_int),('bitmap_bit_order',ctypes.c_int),('bitmap_pad',ctypes.c_int),('depth',ctypes.c_int),('bytes_per_line',ctypes.c_int),('bits_per_pixel',ctypes.c_int),('red_mask',ctypes.c_ulong),('green_mask',ctypes.c_ulong),('blue_mask',ctypes.c_ulong),('obdata',ctypes.c_void_p),('funcs',ctypes.c_void_p*6)]
x=ctypes.CDLL(ctypes.util.find_library('X11'))
x.XOpenDisplay.argtypes=[ctypes.c_char_p]; x.XOpenDisplay.restype=ctypes.c_void_p
x.XGetImage.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_int,ctypes.c_uint,ctypes.c_uint,ctypes.c_ulong,ctypes.c_int]; x.XGetImage.restype=ctypes.POINTER(XImage)
d=x.XOpenDisplay(b':0')
if not d: raise SystemExit('XOpenDisplay failed')
im=x.XGetImage(d,wid,0,0,w,h,ctypes.c_ulong(-1).value,2)
if not im: raise SystemExit('XGetImage failed')
i=im.contents
raw=ctypes.string_at(i.data,i.bytes_per_line*i.height)
bytespp=(i.bits_per_pixel+7)//8

def channel(value,mask):
    if not mask:return 0
    shift=(mask & -mask).bit_length()-1
    vmax=mask>>shift
    return ((value & mask)>>shift)*255//vmax
rows=[]
for y in range(h):
    row=bytearray([0])
    start=y*i.bytes_per_line
    for xx in range(w):
        pos=start+xx*bytespp
        v=int.from_bytes(raw[pos:pos+bytespp], 'little' if i.byte_order==0 else 'big')
        row.extend((channel(v,i.red_mask),channel(v,i.green_mask),channel(v,i.blue_mask)))
    rows.append(bytes(row))
def chunk(tag,data): return struct.pack('!I',len(data))+tag+data+struct.pack('!I',zlib.crc32(tag+data)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows),6))+chunk(b'IEND',b'')
open(out,'wb').write(png)
print(json.dumps({'window':wid,'width':w,'height':h,'depth':i.depth,'bpp':i.bits_per_pixel,'stride':i.bytes_per_line,'masks':[hex(i.red_mask),hex(i.green_mask),hex(i.blue_mask)],'bytes':len(png),'output':out}))
