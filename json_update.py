
import json

"""
Current JSON:
{
  guild_id: {
    channel_pairs: {}
    cleanlinks: {}
    draglinks: {}
    raidstream: int
    raiderrole: int
    vetrole: int
    maxvccap: int
    minvccap: int
    vetchannels: []
    unlockables: []
    maxvetcap: int
    minvetcap: int
  }
}

New JSON:
{
  guild_id: {
    raidstream: int
    raiderrole: int
    vetrole: int
    sections: {
      events/raiding/vet: {
        cmd_ch: int
        status_ch: int
        lounge_ch: int
        voice_chs: list
        drag_chs: list # should be the same number of drag_ch as voice_ch if drag_ch exists
        is_vet: bool
        allow_unlock: bool
        allow_setcap: bool
        max_vc_cap: int
        min_vc_cap: int
      }
    }
  }
}
"""
d = {
  "850544046711111680": {
    "raidstream": 928814688211456081,
    "raiderrole": 923607495400890399,
    "vetrole": 923607528930152468,
    "sections": {
      "event": {
        "cmd_ch": 924097606706135070,
        "status_ch": 924097629594468403,
        "min_role_tier": 1,
        "lounge_ch": 930409057834131527,
        "voice_chs": [930409314529726494, 930410060327301172],
        "drag_chs": None,
        "is_vet": False,
        "allow_unlock": True,
        "allow_setcap": True,
        "max_vc_cap": 50,
        "min_vc_cap": 25,
        "dungeon_blacklist": ['shatters']
      },
      "raiding": {
        "cmd_ch": 930409572252921916,
        "status_ch": 930409557052755988,
        "min_role_tier": 2,
        "lounge_ch": 930409879179513866,
        "voice_chs": [930410095437807646],
        "drag_chs": [930409998650068993],
        "is_vet": False,
        "allow_unlock": False,
        "allow_setcap": False,
        "max_vc_cap": 50,
        "min_vc_cap": 30,
        "dungeon_whitelist": ['shatters']
      },
      "veteran": {
        "cmd_ch": 930410676353138689,
        "status_ch": 930410661916340254,
        "min_role_tier": 3,
        "lounge_ch": 930410700273250314,
        "voice_chs": [930410772478193724],
        "drag_chs": [930410727422967828],
        "is_vet": True,
        "allow_unlock": False,
        "allow_setcap": True,
        "max_vc_cap": 50,
        "min_vc_cap": 15
      }
    }
  },
  
  "451171819672698920": {
    "raidstream": 922587455276851272,
    "raiderrole": 451176397206061056,
    "vetrole": 611399356842508298,
    "sections": {
      "event": {
        "cmd_ch": 672664112114696202,
        "status_ch": 830616025262719006,
        "min_role_tier": 1,
        "lounge_ch": 881724789117575169,
        "voice_chs": [924556564017315900, 911755108243632249, 905887814586085386, 893986445780467773, 886588257029214269],
        "drag_chs": None,
        "is_vet": False,
        "allow_unlock": True,
        "allow_setcap": True,
        "max_vc_cap": 50,
        "min_vc_cap": 25,
        "dungeon_blacklist": ['shatters']
      },
      "raiding": {
        "cmd_ch": 451188304566681600,
        "status_ch": 451181425115398184,
        "min_role_tier": 2,
        "lounge_ch": 451177775706013697,
        "voice_chs": [924549298602004510, 924442912077541426, 924445669199065108, 922958406514520144, 894486438362640415],
        "drag_chs": [710414080263061514, 710415870010195978, 786217397178597426, 788145657696616449, 796881620375437322],
        "is_vet": False,
        "allow_unlock": False,
        "allow_setcap": False,
        "max_vc_cap": 50,
        "min_vc_cap": 30,
        "dungeon_whitelist": ['shatters']
      },
      "veteran": {
        "cmd_ch": 559095494417055759,
        "status_ch": 559095243660722196,
        "min_role_tier": 3,
        "lounge_ch": 824708565494792222,
        "voice_chs": [924508167872852048, 881257871642337342, 880528737454657586, 904514164351983616],
        "drag_chs": [797062027230707752, 798359528999485441, 797062070829842452, 853244780796444682],
        "is_vet": True,
        "allow_unlock": False,
        "allow_setcap": True,
        "max_vc_cap": 50,
        "min_vc_cap": 15
      }
    }
  }
}

with open("database.json", "w") as f:
  f.write(json.dumps(d))