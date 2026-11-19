"""Original Blue Flower film, authored with nested parts and no generated frames."""
from pathlib import Path

from .models import Sequence

ART = Path(__file__).with_name("art")


def track(frame_values, **base):
    """Expand sparse artistic directions to the editable full-pose keyframe format."""
    values = dict(base)
    result = []
    for frame, changes in frame_values:
        values.update({k: v for k, v in changes.items() if k != "ease"})
        result.append({**values, "frame": frame, "ease": changes.get("ease", "smooth")})
    return result


def layer(key, name, asset=None, *, parent=None, pivot=(0, 0), motion=(), **pose):
    return {"id": key, "name": name, "asset": f"bf-{asset}" if asset else None, "parent": parent,
            "pivot_x": pivot[0], "pivot_y": pivot[1], "pose": pose, "keys": track(motion, **pose)}


def toggle(*frames):
    return [(index, {"visible": value, "ease": "hold"}) for index, value in frames]


def blossom(x, y, scale, *, macro=False):
    pulse = [(24, {"opacity": .94, "scale_x": 1.16, "scale_y": 1.16}), (60, {"opacity": .74, "scale_x": 1.02, "scale_y": 1.02})] if macro else []
    return [layer("flower", "Blue flower · root", x=x, y=y, scale_x=scale, scale_y=scale),
            layer("halo", "Reflected blue light", "halo", parent="flower", x=-134, y=-134, opacity=.74, motion=pulse),
            layer("stem", "Stem and leaves", "stem", parent="flower", x=-66, y=-4),
            layer("petals", "Blue petals", "petals", parent="flower", pivot=(60,60),
                  motion=[(0,{"rotation":-3}),(35,{"rotation":4,"scale_x":1.042,"scale_y":1.042}),(71,{"rotation":0})] if macro else ())]


def traveler(*, close):
    blink = [(23,{"scale_y":1}), (27,{"scale_y":.08}), (28,{"visible":False,"ease":"hold"}),
             (33,{"visible":True,"ease":"hold"}), (38,{"scale_y":1})] if close else []
    head = [(31,{"rotation":0}), (54,{"rotation":-7}), (76,{"rotation":-3}), (112,{"rotation":4})] if close else [(0,{"rotation":4}), (68,{"rotation":0})]
    reach = [(33,{"rotation":22}), (62,{"rotation":-42}), (78,{"rotation":-37}), (116,{"rotation":-2})] if close else [(0,{"rotation":25}),(70,{"rotation":18})]
    return [
        layer("shadow", "Ground shadow", "shadow", x=87, y=764, opacity=.66),
        layer("mina", "Mina · body rig", x=83, y=461, motion=[(42,{}), (66,{"x":88,"y":456}), (102,{"x":86,"y":460})] if close else [(0,{"y":467}),(72,{"y":461})]),
        layer("torso", "Cape, body and boots", "torso", parent="mina", x=4, y=154),
        layer("head", "Head tilt · neck pivot", parent="mina", x=90, y=168, motion=head),
        layer("face", "Face and back hair", "face", parent="head", x=-78, y=-152),
        layer("brows", "Eyebrow expression", "brows", parent="head", x=-46, y=-78,
              motion=[(43,{}),(65,{"y":-82,"rotation":-4}),(100,{"y":-79,"rotation":0})] if close else ()),
        layer("eyes", "Eyes · blink track", "eyes", parent="head", x=-4, y=-42, pivot=(54,18), motion=blink),
        layer("lids", "Closed eyelids", "lids", parent="head", x=-58, y=-60, visible=False,
              motion=toggle((28,True),(33,False)) if close else ()),
        layer("smile", "Smile", "smile", parent="head", x=-12, y=-24,
              motion=toggle((51,False),(84,True)) if close else ()),
        layer("mouth", "Wonder · open mouth", "mouth", parent="head", x=-12, y=-24, visible=False,
              motion=toggle((51,True),(84,False)) if close else ()),
        layer("fringe", "Fringe and star pin", "fringe", parent="head", x=-78, y=-150),
        layer("arm", "Reaching arm · shoulder pivot", parent="mina", x=133, y=187, rotation=22, motion=reach),
        layer("sleeve", "Sleeve", "sleeve", parent="arm", x=-14, y=-10),
        layer("hand", "Hand · wrist pivot", "hand", parent="arm", x=43, y=18, pivot=(5,13),
              motion=[(46,{}),(69,{"rotation":-18}),(83,{"rotation":8}),(112,{"rotation":0})] if close else ()),
    ]


def blue_flower() -> Sequence:
    forest = lambda: layer("forest", "Twilight forest · background", "forest")
    foreground = lambda: layer("ferns", "Ferns · foreground", "foreground", y=728)
    return Sequence.model_validate({"title": "Blue Flower", "shots": [
        {"id": "approach", "name": "The woodland path", "frames": 96,
         "camera": {"mode": "keyframed", "pose": {"x":270,"y":480,"zoom":1},
                    "keys": [{"frame":95,"x":274,"y":510,"zoom":1.08}]},
         "layers": [forest(), *blossom(350,663,.75), *traveler(close=False), foreground(),
                    layer("glimmer", "Drifting glimmer", "spark", pivot=(28,28), x=334, y=623, opacity=.55,
                          motion=[(70,{"x":343,"y":600,"opacity":.85}),(95,{"opacity":.49})])]},
        {"id": "reach", "name": "Mina notices the light", "frames": 120,
         "camera": {"mode": "locked", "pose": {"x":251,"y":586,"zoom":1.40}},
         "layers": [forest(), *blossom(350,663,.75), *traveler(close=True), foreground()]},
        {"id": "bloom", "name": "Into the bloom", "frames": 78,
         "camera": {"mode": "keyframed", "pose": {"x":270,"y":479,"zoom":1.035},
                    "keys": [{"frame":77,"x":270,"y":488,"zoom":1.12}]},
         "layers": [layer("detail", "Forest bokeh · background", "glade-detail"), *blossom(271,411,2.28,macro=True),
                    layer("drift-one", "Petal glint", "spark", pivot=(28,28), x=189, y=348, opacity=.4,
                          motion=[(40,{"x":178,"y":313,"opacity":.98}),(77,{"x":164,"y":283,"opacity":.18})]),
                    layer("drift-two", "Floating light", "spark", pivot=(28,28), x=327, y=422, opacity=.31,
                          motion=[(62,{"x":391,"y":345,"opacity":.78}),(77,{"opacity":.27})])]},
    ]})
