from pathlib import Path

from SourceIO.utilities.datamodel import DataModel, load, Color, _dmxtypes, _dmxtypes_all, _dmxtypes_str, Element
import sys


class FixedColor(Color):

    def __repr__(self):
        return " ".join([str(int(ord)) for ord in self])


class EmptyElement(Element):

    def get_kv2(self, deep=True):
        return ''

    def __repr__(self):
        return ''


_dmxtypes.append(FixedColor)
_dmxtypes_all.append(FixedColor)
_dmxtypes_str.append('color')

_dmxtypes.append(EmptyElement)
_dmxtypes_all.append(EmptyElement)
_dmxtypes_str.append('element')

if __name__ == '__main__':

    if len(sys.argv) != 2:
        dmx_file = input("Source2 camera animation DMX file:")
        # print("Provide exactly 1 camera animation dmx file as an argument!")
    else:
        dmx_file = sys.argv[1]
    dmx_file = dmx_file.strip('"\'')

    s2 = load(dmx_file)
    # s1 = load(r"C:\Users\MED45\Downloads\p1_s2_camera_steamvr_-_Copy.dmx")

    for elem in s2.find_elements(elemtype='DmeChannelsClip'):
        elem['color'] = FixedColor([int(a) for a in elem['color']])


    def get_elemnts(elem_type):
        return s2.find_elements(elemtype=elem_type) or []


    elements_to_fix = get_elemnts('DmeFloatLog') + \
                      get_elemnts('DmeVector3Log') + \
                      get_elemnts('DmeQuaternionLog') + \
                      get_elemnts('DmeBoolLog')

    for elem in elements_to_fix:
        if elem['curveinfo'] is None:
            elem['curveinfo'] = EmptyElement(s2, '', 'element')

    elements_to_fix = get_elemnts('DmeChannel')

    for elem in elements_to_fix:
        if elem['fromElement'] is None:
            elem['fromElement'] = EmptyElement(s2, '', 'element')
        if elem['toElement'] is None:
            elem['toElement'] = EmptyElement(s2, '', 'element')

    elements_to_fix = get_elemnts('DmeCamera')

    for elem in elements_to_fix:
        if elem['shape'] is None:
            elem['shape'] = EmptyElement(s2, '', 'element')

    s2.format_ver = 18
    path = Path(dmx_file)
    path = path.with_name(path.stem + "_s1cvt").with_suffix('.dmx')
    s2.write(path, 'keyvalues2', 1)
