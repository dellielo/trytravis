from collections import namedtuple 

list_key = {"name": "", "category": "CATEGORY", "rect": "RECT"}

Info = namedtuple("Info", ("name", "category", "rect"))
info = Info("IMG_01", "Vehicle", "(12,15,25,65)")

# pattern = "{name}"+ "".join( "%s;{%s}" % (v, k) for k,v in list_key[1:].items())

pattern = "{name} CATEGORY;{category} RECT;{rect} LABEL;{label:0}" #" LABEL;{label} TIME;{time} "
# #rect = (12,15,25,65) -> "12,15,25,65"
# pattern = "%s CATEGORY;%s RECT;%s LABEL;%s TIME;%s "
# list_key = ["NAME", "CAT", "RECT", "LABEL", "TIME"]
# list_value = [for k,v in info.as_dict()]

line = pattern.format(**info._asdict())
print (line)

