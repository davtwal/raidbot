from discord import Emoji
from typing import Dict, List, Tuple

HC_TEXT_GENERIC = """
A {} headcount has been started by {}.
React with {} if you plan to join.
React with {} if you have a key.
Otherwise react with your role, gear, and class choices below.
"""

AFK_TEXT_GENERIC = """
A {} raid has been started by {} in {}.
React with {} if you plan to join.
React with {} and confirm if you have a key.
Otherwise, react with your role, gear, and class choices below.
"""

# portal emoji, dungeon name, rl mention
HC_TITLE_GENERIC = "Headcount for {} by {}"

# Base Dungeon class
class Dungeon:
  # Early reacts are reacts that give early location.
  # == Early: {REACT: [max count, role_required]}
  # Primary reacts are reacts that are dragged in for lazy AFKs.
  # Secondary reacts are other reacts.
  
  def __init__(self, name:str, 
               portal_reacts:List[int],
               key_reacts:List[int],
               early_reacts:Dict[int, Tuple[int, str]]=None,
               primary_reacts:List[int]=None,
               secondary_reacts:List[int]=None,
               max_keys:int=0):
    assert portal_reacts is not None
    assert key_reacts is not None
    self.code = None
    self.name = name
    self.react_portals = portal_reacts
    self.react_keys = key_reacts
    self.react_early = early_reacts
    self.react_primary = primary_reacts
    self.react_secondary = secondary_reacts
    self.max_keys = max_keys
  
  def _build_portal_emoji(self, bot):
    portal = bot.get_emoji(self.react_portals[0])
    if portal is None:
      portal = '🔵'
    return str(portal)
  
  def _build_key_emoji(self, bot):
    key_emoji_str = ""
    for key in self.react_keys:
      keymoji = bot.get_emoji(key)
      if keymoji is None:
        if key_emoji_str == "":
          key_emoji_str = "🔑"
          break
        else:
          continue
        
      key_emoji_str += str(keymoji)
    return key_emoji_str
  
  def _build_emoji_list(self, bot, id_list):
    retval = []
    for react in id_list:
      retval.append(bot.get_emoji(react))
    return retval
  
  def get_portal_react_emojis(self, bot) -> List[Emoji]:
    return [] if self.react_portals is None else [bot.get_emoji(react) for react in self.react_portals]

  def get_key_react_emojis(self, bot) -> List[Emoji]:
    return [] if self.react_keys is None else [bot.get_emoji(react) for react in self.react_keys]
  
  def get_early_react_emojis(self, bot) -> List[Emoji]:
    return [] if self.react_early is None else [bot.get_emoji(react) for react in self.react_early]
  
  def get_primary_react_emojis(self, bot) -> List[Emoji]:
    return [] if self.react_primary is None else [bot.get_emoji(react) for react in self.react_primary]
  
  def get_secondary_react_emojis(self, bot) -> List[Emoji]:
    return [] if self.react_secondary is None else [bot.get_emoji(react) for react in self.react_secondary]
  
  def get_hc_text(self, bot, rl):
    portal = self._build_portal_emoji(bot)
    keys = self._build_key_emoji(bot)
    return HC_TEXT_GENERIC.format(self.name, rl.mention, portal, keys)
  
  def get_afk_text(self, bot, rl, voice_ch):
    portal = self._build_portal_emoji(bot)
    keys = self._build_key_emoji(bot)
    return AFK_TEXT_GENERIC.format(self.name, rl.mention, voice_ch.mention, portal, keys)
  
  def get_hc_title(self, bot, rl):
    #portal = self._build_portal_emoji(bot)
    return HC_TITLE_GENERIC.format(self.name, rl.display_name)
  
  def get_hc_reacts(self):
    retval = self.react_portals + self.react_keys
    if self.react_early:
      retval += self.react_early.keys()
    if self.react_primary:
      retval += self.react_primary
    if self.react_secondary:
      retval += self.react_secondary
    return retval
  
  def get_code(self):
    for dtype in dungeonlist:
      for d in dungeonlist[dtype]:
        if dungeonlist[dtype][d].name == self.name:
          return d
    return None
  
  def get_key_names(self):
    return ['Key']
  
  def set_code(self, code):
    self.code = code

HC_TEXT_VOID = """A {} headcount has been started by {}.
React with {} if you plan to join.
React with {} if you have a key.
React with {} if you have a vial.
Otherwise react with your role, gear, and class choices below."""

AFK_TEXT_VOID = """A {} raid has been started by {} in {}.
React with {} if you plan to join.
React with {} and confirm if you have a key.
React with {} and confirm if you have a vial.
Otherwise react with your role, gear, and class choices below."""
class VoidDungeon(Dungeon):
  def get_hc_text(self, bot, rl):
    portal = self._build_portal_emoji(bot)
    key = bot.get_emoji(self.react_keys[0])
    vial = bot.get_emoji(self.react_keys[1])
    return HC_TEXT_VOID.format(self.name, rl.mention, portal, key, vial)
  
  def get_afk_text(self, bot, rl, voice):
    portal = self._build_portal_emoji(bot)
    key = bot.get_emoji(self.react_keys[0])
    vial = bot.get_emoji(self.react_keys[1])
    return AFK_TEXT_VOID.format(self.name, rl.mention, voice.mention, portal, key, vial)
  
  def get_key_names(self):
    return ['Key', 'Vial']

HC_TEXT_OSANC = """A {} headcount has been started by {}.
React with {} if you plan to join.
React with {} if you have an inc.
React with {}{}{} if you have rune(s).
Otherwise react with your role, gear, and class choices below."""

AFK_TEXT_OSANC = """An {} raid has been started by {} in {}.
React with {} if you plan to join.
Press {} and confirm if you have an inc.
Press {}{}{} and confirm if you have rune(s).
Otherwise react with your role, gear, and class choices below."""
class SanctuaryDungeon(Dungeon):
  def get_hc_text(self, bot, rl):
    portal = self._build_portal_emoji(bot)
    inc = bot.get_emoji(self.react_keys[0])
    runes = [bot.get_emoji(self.react_keys[i]) for i in range(1,4)]
    return HC_TEXT_OSANC.format(self.name, rl.mention, portal, inc, *runes)
  
  def get_afk_text(self, bot, rl, voice):
    portal = self._build_portal_emoji(bot)
    inc = bot.get_emoji(self.react_keys[0])
    runes = [bot.get_emoji(self.react_keys[i]) for i in range(1,4)]
    return AFK_TEXT_OSANC.format(self.name, rl.mention, voice.mention, portal, inc, *runes)
  
  def get_key_names(self):
    return ['Inc', 'Sword', 'Helm', 'Shield']

R_BERSERK = 924760618714685501
R_DAMAGING = 924760618941182002
R_INSPIRE = 924760618572066827

R_STUN = 924760619025055834
R_CURSE = 924760618861482024
R_ARMORBREAK = 924760618840514611
R_EXPOSE = 924760618957946910
R_DAZE = 924760618953748490
R_SLOW = 924760619121541221

R_MSEAL = 924776847248621568
R_AETHER = 924776847223427112
R_CSHIELD = 924776847298920468
R_FUNGAL = 924780902591119422

R_RUSH = 924782643797704705
# TODO: Make this not dependent on Shatters server
R_SWITCHRUSH = 888889860964892693

R_WARRIOR = 924760732170600469
R_PALADIN = 924760732195758100
R_KNIGHT = 924760731939901451
R_TRICKSTER = 924760732187381820
R_MYSTIC = 924760732090896445

DUNGEON_EMOTE_NAMES = {
  R_BERSERK: 'Berserk',
  R_DAMAGING: 'Damaging',
  R_INSPIRE: 'Inspire',
  R_STUN: 'Stun',
  R_CURSE: 'Curse',
  R_ARMORBREAK: 'Armor Break',
  R_EXPOSE: 'Expose',
  R_DAZE: 'Daze',
  R_SLOW: 'Slow',
  R_MSEAL: 'M. Seal',
  R_AETHER: 'Aether',
  R_CSHIELD: 'C. Shield',
  R_FUNGAL: 'Fungal',
  R_RUSH: 'Rusher',
  R_WARRIOR: 'Warrior',
  R_PALADIN: 'Paladin',
  R_KNIGHT: 'Knight',
  R_TRICKSTER: 'Trickster',
  R_MYSTIC: 'Mystic',
  R_SWITCHRUSH: 'Switch Rusher'
}

buffs = [R_BERSERK, R_DAMAGING, R_INSPIRE]
dps_debuff = [R_CURSE, R_ARMORBREAK, R_EXPOSE]
standard_buffs = [R_BERSERK, R_DAMAGING, R_INSPIRE, R_STUN, R_CURSE, R_ARMORBREAK, R_EXPOSE]

SHATTERS_DNAME = 'shatters'
OSANC_DNAME = 'o3'
FUNGAL_DNAME = 'fungal'
NEST_DNAME = 'nest'
CULT_DNAME = 'cult'
VOID_DNAME = 'void'

dungeonlist: Dict[str, Dict[str, Dungeon]] = {
  'Basic': {
    'pcave': Dungeon('Pirate Cave', [924101782714597408], [924723992785465376], None, None, standard_buffs),
    'fmaze': Dungeon('Forest Maze', [924101783008206919], [924723992965820416], None, None, standard_buffs),
    'sden': Dungeon('Spider Den',   [924101783079485440], [924723993083252827], None, None, standard_buffs),
    'snake': Dungeon('Snake Pit',   [924101782999814174], [924723993125195776], None, None, standard_buffs),
    'fjungle': Dungeon('Jungle',    [924711829203210321], [924723992739315713], None, None, standard_buffs),
    'hive': Dungeon('Hive',         [924396141552992256], [924723993049694228], None, None, standard_buffs)
  },
  'Godlands': {
    'mwoods': Dungeon('Magic Woods',  [924396141632704512], [924724313972699226], None, None, standard_buffs),
    'sprite': Dungeon('Sprite',       [924712495808135179], [924723993091645530], None, None, standard_buffs),
    'cland': Dungeon('Candyland',     [924396141183893556], [924723993204908042], None, None, standard_buffs),
    'ruins': Dungeon('Ruins',         [924396141699805235], [924723993053909052], None, None, standard_buffs),
    'tcave': Dungeon('Treasure Cave', [924712708824236092], [924723993104224266], None, None, standard_buffs),
    'abyss': Dungeon('Abyss',         [924709171469910036], [924723992630280203], None, None, standard_buffs),
    'manor': Dungeon('Manor',         [924101782714597408], [924723992974200862], None, None, standard_buffs),
    'theater': Dungeon('Theater',     [924712859609477200], [924723993267806208], None, None, standard_buffs),
    'sewer': Dungeon('Toxic Sewers',  [924712905042174072], [924723993070682132], None, None, standard_buffs),
    'lib': Dungeon('Library',         [924709171377635358], [924723993242640454], None, None, standard_buffs),
    'cem': Dungeon('Cemetery',        [924396141733371914], [924723993095847976], None, [R_AETHER], standard_buffs),
    'mlab': Dungeon('Mad Lab',        [924710140400242698], [924723992915505213], None, None, standard_buffs),
    'para': Dungeon("Parasite",       [924709742708932669], [924723993024544818], None, None, standard_buffs),
    'machine': Dungeon('Machine',     [924709171511848970], [924723992802238536], None, None, standard_buffs)
  },
  'Epic': {
    'ddocks': Dungeon('Docks',    [924713330805977098], [924723992944869396], None, [R_EXPOSE], buffs + [R_STUN, R_CURSE, R_ARMORBREAK]),
    'wlab': Dungeon("Woodland",   [924710140006002759], [924723993792094238], None, None, standard_buffs),
    'cdepths': Dungeon("Depths",  [924710140236668948], [924723992999366656], None, None, standard_buffs)
  },
  'Event': {
    'beachzone': Dungeon('Beachzone',     [924711682973003807], [924723993083269170], None, None, standard_buffs),
    '3d': Dungeon('3D',                   [924711682847170643], [924723992659632259], None, [924780902591119422], standard_buffs),
    'davy': Dungeon('Davy Jone\'s',       [924711683061071952], [924723992978399332], None, None, standard_buffs),
    'mtemple': Dungeon('Mountain Temple', [924711683094609981], [924723993116831784], None, None, standard_buffs),
    'lod': Dungeon('Lair of Draconis',    [924711683027529798], [924723992810623037], None, [R_TRICKSTER], standard_buffs),
    'ot': Dungeon('Ocean Trench',         [924711683065266176], [924723995172032633], None, None, standard_buffs),
    'icecave': Dungeon('Ice Cave',        [924711682989785129], [924723993032945674], None, None, standard_buffs),
    'tomb': Dungeon('Tomb',               [924711683065278464], [924723993834053702], {R_STUN: [2, None], R_AETHER: [2, None]}, None, [R_TRICKSTER] + buffs + dps_debuff)
  },
  'Aliens': {
    #'aliens': Dungeon('Aliens',     [924743856933707816], [924742807007166484, 924742806336061531, 924742806235394069, 924742806789029958], None, standard_buffs),
    'malogia': Dungeon('Malogia',   [924743856736579625], [924742807007166484], None, standard_buffs),
    'untaris': Dungeon('Untaris',   [924743857000841257], [924742806336061531], None, standard_buffs),
    'forax': Dungeon('Forax',       [924743856891777114], [924742806235394069], None, standard_buffs),
    'katalund': Dungeon('Katalund', [924743856866603019], [924742806789029958], None, standard_buffs)
  },
  'Exaltation': {
    FUNGAL_DNAME: Dungeon('Fungal Cavern',  [924714365251362856], [924723992949063730], None, [R_SLOW, R_MSEAL, R_FUNGAL, R_TRICKSTER, R_MYSTIC], standard_buffs),
    NEST_DNAME: Dungeon('Nest',             [924711683409215579], [924723993116803202], None, [R_SLOW, R_DAZE, R_FUNGAL, R_TRICKSTER], standard_buffs),
    SHATTERS_DNAME: Dungeon('Shatters', [924809116755587112], [924723993070682202], {R_SWITCHRUSH: [3, 'Rusher'], R_FUNGAL: [2, 'Supreme Priest']}, [R_MSEAL, R_CSHIELD, R_TRICKSTER, R_SLOW], standard_buffs, 1),
    CULT_DNAME: Dungeon('Cultist Hideout',  [924711683308519515], [924723992621903883], {R_RUSH: [2, None]}, [R_DAZE, R_TRICKSTER], [R_FUNGAL, R_MSEAL] + standard_buffs),
    VOID_DNAME: VoidDungeon('Void',         [924711683161739324], [924723992621903883, 924723993808887849], None, [R_FUNGAL, R_MSEAL], standard_buffs),
    OSANC_DNAME: SanctuaryDungeon('Oryx\'s Sanctuary', [924728919465267232], [924728746785775706, 924723993272004649, 924723992730927157, 924723993079074947], None, [R_TRICKSTER, R_FUNGAL], [R_MSEAL, R_MYSTIC] + standard_buffs)
  },
  'Court': {
    'shaitan': Dungeon('Lair of Shaitain',        [924745735910604820], [924744714425602078], None, [R_MSEAL], standard_buffs),
    'encore': Dungeon('Puppet Master\'s Encore',  [924745735788986418], [924744714576605214], None, None, standard_buffs),
    'reef': Dungeon('Cnidarian Reef',             [924745735809937428], [924744714069102593], None, [R_FUNGAL], standard_buffs),
    'thicket': Dungeon('Secluded Thicket',        [924745735780569128], [924744713968435222], None, [R_FUNGAL], standard_buffs),
    'htt': Dungeon('High Tech Terror',            [924745735734427698], [924744714299777054], None, [R_FUNGAL, R_MSEAL], standard_buffs)
  },
  'Special': {
    'bftn': Dungeon('Battle f.t. Nexus',      [924745735696707625], [924746702383091762], None, None, standard_buffs),
    'bellas': Dungeon('Belladonna\'s Garden', [924745735969333258], [924746702202761256], None, None, standard_buffs),
    'icetomb': Dungeon('Ice Tomb',            [924745735797374976], [924746702534094848], None, [R_AETHER, R_STUN], buffs + dps_debuff + [R_TRICKSTER]),
    'mgm': Dungeon('Mad God Mayhem',          [924745735747014666], [924746702253068348], None, None, standard_buffs)
  }
}

for dtype in dungeonlist:
  for dungeon in dungeonlist[dtype]:
    dungeonlist[dtype][dungeon].set_code(dungeon)

def get(name) -> Dungeon:
  for dtype in dungeonlist:
    if name in dungeonlist[dtype]:
      return dungeonlist[dtype][name]
  
  return None

def get_react_name(react: int, dungeon: Dungeon) -> str:
  if react in DUNGEON_EMOTE_NAMES:
    return DUNGEON_EMOTE_NAMES[react]
  
  if react in dungeon.react_keys:
    return dungeon.get_key_names()[dungeon.react_keys.index(react)]
  
  return None