"""Deterministic, extractive story planning. All proposed labels can be corrected in the studio."""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

from .plan_models import (MAX_CHARACTERS, MAX_DIALOGUE, MAX_PLACES, MAX_PROPS, MAX_SCENES,
                          MIN_GENERATED_SCENE, Appearance, Character, DialogueLine, PlanDocument,
                          PlanSource, Reference, Scene, StoryArc, StoryBible)
from .plan_timing import Cost, distribute, planning_rate, read_cost, with_scene_padding
from .schemas import DraftProfile
from .story_text import EN_NAME, Line, clip, passages, script_hint, separate_speech, words


def key(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text.casefold())
    return normalized.replace("\u200c", "").replace("\u200d", "")


def vocabulary(groups: dict[str, str]) -> dict[str, str]:
    return {key(word): group for group, entries in groups.items() for word in entries.split()}


ROLES = vocabulary({
    "girl": "girl girls लड़की लड़कियाँ बच्ची মেয়ে মেয়েটি মেয়েটি কিশোরী",
    "boy": "boy boys लड़का लड़के बालक ছেলে ছেলেটি বালক",
    "woman": "woman women mother grandmother witch queen औरत महिला माँ रानी মা রানি মহিলা নারী",
    "man": "man men father grandfather king farmer आदमी पुरुष पिता राजा বাবা রাজা মানুষটি",
    "child": "child children kid बच्चा बच्चे শিশु শিশু বাচ্চা",
    "traveler": "traveler traveller wanderer explorer courier यात्री পথিক ভ্রমণকারী",
    "creature": "creature creatures animal जीव प्राणी প্রাণী প্রাণীটি প্রাণীটিকে জীব জন্তু",
    "spirit": "spirit fairy ghost परी आत्मा भूत পরী আত্মা ভূত",
    "fox": "fox foxes लोमड़ी শিয়াল শেয়াল শিয়ালটি",
    "cat": "cat kitten बिल्ली বিড়াল বিড়াল বিড়ালটি",
    "dog": "dog puppy कुत्ता कुत्ते কুকুর কুকুরটি",
    "dragon": "dragon dragons ड्रैगन ড্রাগন",
    "bird": "bird birds crow raven पक्षी चिड़िया পাখি পাখিটি",
    "friend": "friend friends साथी दोस्त বন্ধু বন্ধুটি",
    "rabbit": "rabbit hare खरगोश খরগোশ",
})
PLACES = vocabulary({
    "forest": "forest forests woods woodland jungle जंगल वन জঙ্গল জঙ্গলে বন বনে বনটি বনের",
    "tree": "tree पेड़ वृक्ष গাছ গাছের গাছটি",
    "village": "village hamlet गाँव गांव গ্রাম গ্রামে গ্রামের",
    "city": "city town street शहर नगर শহর শহরে রাস্তা",
    "water": "river lake pond stream नदी तालाब নদী হ্রদ পুকুর",
    "shore": "shore beach coast समुद्र तट সমুদ্র সৈকত তীর",
    "home": "house hut cottage home room cabin घर झोपड़ी कमरा বাড়ি ঘর ঘরে কুটির",
    "cave": "cave tunnel गुफा सुरंग গুহা সুড়ঙ্গ",
    "pass": "mountain hill valley pass पर्वत पहाड़ घाटी পাহাড় পাহাড় উপত্যকা",
    "garden": "garden orchard meadow field बगीचा मैदान বাগান মাঠ",
    "station": "station स्टेशन স্টেশন",
    "bridge": "bridge पुल সেতু",
    "palace": "palace castle महल কেল্লা প্রাসাদ",
})
PROPS = vocabulary({
    "flower": "flower flowers bloom फूल पुष्प ফুল ফুলটি",
    "lantern": "lantern lanterns torch lamp दीपक लालटेन লণ্ঠন বাতি",
    "letter": "letter letters envelope note चिट्ठी पत्र চিঠি চিঠিটি",
    "key": "key keys चाबी চাবি চাবিটি",
    "book": "book books map किताब पुस्तक नक्शा বই বইটি মানচিত্র",
    "boat": "boat canoe नाव नाँव নৌকা নৌকাটি",
    "light": "lights रोशनी আলো আলোয় আলোয় আলোগুলো",
    "stone": "stone gem jewel crystal पत्थर रत्न পাথর রত্ন",
    "ring": "ring amulet अंगूठी আংটি তাবিজ",
    "clock": "clock wristwatch timepiece घड़ी ঘড়ি",
    "bell": "bell bells घंटी ঘণ্টা",
    "seed": "seed seeds बीज বীজ",
})
QUALIFIERS = set("little chibi young old tiny magical shy brave curious small mysterious glowing blue red white golden silver "
                 "ancient abandoned enchanted dark misty paper violet broken lost redwood stone wooden quiet lonely "
                 "छोटी छोटा चमकता चमकती चमकीला नीला नीली नन्हा नन्हे जादुई पुराना पुराने रहस्यमय "
                 "ছোট ছোট্ট জ্বলজ্বলে উজ্জ্বল নীল রহস্যময় জাদুকরী পুরনো পুরোনো অদ্ভুত বিশাল".split())
DRAMA = vocabulary({
    "concern": "trapped stuck danger threatened frightened afraid terrified lost blocked worry फँसे फँसी फंसा डर खतरा আটক আটকে ভয় বিপদ হারিয়ে",
    "relief": "helps helped saves saved rescues rescued freed frees escapes reunited बचाती बचाया बचाता छुड़ाया मुक्त বাঁচায় বাঁচাল উদ্ধার সাহায্য মুক্ত",
    "wonder": "illuminated glow glowed glowing sparkling magical lights wonder जगमग रोशनी चमक उजाला আলো জ্বলে আলোকিত জাদু",
    "curiosity": "finds found discovers discovered follows wondered looks खोजती पाया मिलता খুঁজে পায় অনুসরণ",
    "joy": "smiled smiles laughed joy happy मुस्कुराई खुशी হাসল হাসি আনন্দ",
    "sadness": "cried wept sad tears sorrow आँसू उदास কাঁদল দুঃখ",
})
PRONOUNS = {"i", "me", "he", "she", "him", "her", "they", "them", "it", "we", "you", "वह", "उसने", "वे", "সে", "তিনি", "তারা"}
FEMININE = {"she", "her"}
MASCULINE = {"he", "him"}
NAME_CONTEXT = re.compile(rf"\b({EN_NAME})\s+(?i:said|says|walked|walks|runs|ran|finds|found|sees|saw|takes|took|opens|opened|steps|stepped|discovers|discovered|asks|asked|enters|entered|looks|looked|helps|helped|waits|waited|followed|follows|whispered|travels|lives|rescued)\b")
NAME_AFTER = re.compile(rf"\b(?i:met|named|called|greeted)\s+({EN_NAME})\b")
NOT_NAMES = {"the", "a", "an", "then", "after", "before", "finally", "later", "suddenly", "when", "once", "but", "and", "now"} | PRONOUNS
STYLES = {
    "storybook": "Watercolor storybook anime; whimsical hand-painted scenery and soft cinematic lighting",
    "cel": "Cel-shaded Japanese anime-inspired 2D art; clean silhouettes and expressive lighting",
    "moonlit": "Moonlit ink illustration; soft color washes, detailed environments and restrained highlights",
}
MOVEMENT = {
    "subtle": "Use a restrained 2D camera move and a mostly still illustration.",
    "balanced": "Use a smooth 2D camera move; add gentle parallax if separate layers are available.",
    "expressive": "Use a more pronounced 2D camera move with a smooth ease; layer atmosphere if the illustration permits it.",
}


@dataclass(frozen=True)
class Mention:
    key: str
    label: str


@dataclass
class Beat:
    source: str
    narration: str
    dialogue: list[Line]
    tokens: list[str]
    cast: list[Mention]
    places: list[Mention]
    props: list[Mention]
    moods: set[str]
    voice: Cost
    dialogue_cost: Cost
    spoken_dialogue_count: int


@dataclass
class Allocation:
    indexes: list[int] = field(default_factory=list)
    narration: Cost = field(default_factory=Cost)
    dialogue: Cost = field(default_factory=Cost)
    dialogue_rows: int = 0
    spoken_dialogue_rows: int = 0
    narration_length: int = 0
    minimum: int = MIN_GENERATED_SCENE


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:]


def find_mentions(tokens: list[str], normalized: list[str], table: dict[str, str]) -> list[Mention]:
    found: dict[str, Mention] = {}
    for index, word in enumerate(normalized):
        kind = table.get(word)
        if not kind or kind in found:
            continue
        start = index
        while start > max(0, index - 4) and normalized[start - 1] in QUALIFIERS:
            start -= 1
        found[kind] = Mention(kind, clip(sentence_case(" ".join(tokens[start:index + 1])), 120))
    return list(found.values())


def name_key(name: str) -> str:
    return ROLES.get(key(name), f"named:{key(name)}")


def guess_names(source: str, dialogue: list[Line]) -> list[Mention]:
    proposed = [match[1] for rule in (NAME_CONTEXT, NAME_AFTER) for match in rule.finditer(source)]
    proposed.extend(line.speaker for line in dialogue if line.speaker)
    names = []
    for proposal in proposed:
        tokens = words(proposal)
        if len(tokens) > 1 and key(tokens[0]) in NOT_NAMES:
            tokens = tokens[1:]
        if tokens and all(key(token) not in NOT_NAMES and key(token) not in PLACES and key(token) not in PROPS for token in tokens):
            label = " ".join(tokens)
            names.append(Mention(name_key(label), label))
    return names


def parse_beat(part: str, rate: int) -> Beat:
    narration, dialogue = separate_speech(part)
    tokens = words(narration or part)
    normalized = [key(token) for token in tokens]
    candidates: dict[str, Mention] = {}
    for item in find_mentions(tokens, normalized, ROLES) + guess_names(narration, dialogue):
        candidates.setdefault(item.key, item)
    cast = list(candidates.values())
    costs = [read_cost(line.text, rate) for line in dialogue]
    return Beat(source=part, narration=narration, dialogue=dialogue, tokens=normalized, cast=cast,
                places=find_mentions(tokens, normalized, PLACES), props=find_mentions(tokens, normalized, PROPS),
                moods={DRAMA[token] for token in normalized if token in DRAMA},
                voice=read_cost(narration, rate), dialogue_cost=sum(costs, Cost()), spoken_dialogue_count=sum(bool(cost.words) for cost in costs))


def unique(items):
    return list(dict.fromkeys(items))


def catalog(beats: list[Beat], kind: str, limit: int) -> dict[str, Mention]:
    entries: dict[str, Mention] = {}
    for beat in beats:
        for mention in getattr(beat, kind):
            if mention.key not in entries and len(entries) < limit:
                entries[mention.key] = mention
    return entries


def first_trigger(beats: list[Beat], cue: str, start: int = 0) -> int | None:
    return next((index for index in range(start, len(beats)) if cue in beats[index].moods), None)


def arc_for(beats: list[Beat], conflict: int | None, climax: int | None) -> StoryArc:
    highlights = sorted(unique([0, conflict if conflict is not None else len(beats) // 2,
                                climax if climax is not None else len(beats) - 1, len(beats) - 1]))
    moods = []
    for beat in beats:
        highlights_for_beat = (["concern"] if "concern" in beat.moods else
                               [cue for cue in ("relief", "wonder", "joy") if cue in beat.moods] if "relief" in beat.moods else
                               [next((cue for cue in ("sadness", "curiosity", "joy", "wonder") if cue in beat.moods), "")])
        for mood in highlights_for_beat:
            if mood and (not moods or moods[-1] != mood.title()):
                moods.append(mood.title())
    peak = beats[climax].source if climax is not None else ""
    if climax is not None and climax == len(beats) - 1:
        peak = re.split(r"[,;।]", peak, maxsplit=1)[0]
    return StoryArc(main_plot=" ".join(clip(beats[index].source, 360) for index in highlights),
                    beginning=clip(beats[0].source, 900), conflict=clip(beats[conflict].source, 900) if conflict is not None else "",
                    emotional_development=clip(" → ".join(moods), 1600), climax=clip(peak, 900), ending=clip(beats[-1].source, 900))


def preferred_beat(beats: list[Beat], start: int, end: int, index: int, count: int,
                   conflict: int | None, climax: int | None) -> int:
    if index == 0:
        return start
    if index == count - 1:
        return end - 1
    for important in (conflict, climax):
        if important is not None and start <= important < end:
            return important
    return max(range(start, end), key=lambda position: (bool(beats[position].places or beats[position].props),
                                                       bool(beats[position].moods), min(beats[position].voice.words, 24)))


def try_take(allocation: Allocation, beat: Beat, index: int, spare: int) -> int:
    if not beat.voice.words and not beat.spoken_dialogue_count:
        return 0
    size = allocation.narration_length + len(beat.narration) + bool(allocation.narration_length and beat.narration)
    dialogue_rows = allocation.dialogue_rows + len(beat.dialogue)
    if size > 8000 or dialogue_rows > MAX_DIALOGUE or any(len(line.text) > 1800 for line in beat.dialogue):
        return 0
    voice = allocation.narration + beat.voice
    dialogue = allocation.dialogue + beat.dialogue_cost
    lines = allocation.spoken_dialogue_rows + beat.spoken_dialogue_count
    estimate = with_scene_padding(voice, dialogue, lines)
    floor = max(MIN_GENERATED_SCENE, math.ceil(estimate.ms / 1000))
    increase = floor - allocation.minimum
    if increase > spare:
        return 0
    allocation.indexes.append(index)
    allocation.narration, allocation.dialogue = voice, dialogue
    allocation.dialogue_rows, allocation.spoken_dialogue_rows = dialogue_rows, lines
    allocation.narration_length, allocation.minimum = size, floor
    return increase


def build_plan(story: str, profile: DraftProfile) -> tuple[PlanDocument, PlanSource]:
    segments = passages(story)
    if not segments:
        raise ValueError("Add some story text with words before generating a plan.")
    rate = planning_rate(story, profile.language)
    beats = [parse_beat(part, rate) for part in segments]
    target, length = profile.duration_seconds, len(beats)
    count = min(length, MAX_SCENES, target // MIN_GENERATED_SCENE, max(1, round(target / 8.5)))
    starts = [index * length // count for index in range(count + 1)]
    rows = [Allocation() for _ in range(count)]
    slot_for = [index for index in range(count) for _ in range(starts[index], starts[index + 1])]
    conflict = first_trigger(beats, "concern")
    climax = first_trigger(beats, "relief", conflict if conflict is not None else 0)
    anchors = [preferred_beat(beats, starts[index], starts[index + 1], index, count, conflict, climax) for index in range(count)]
    spare = target - count * MIN_GENERATED_SCENE
    order = unique(index for index in [0, length - 1, conflict, climax, *anchors, *range(length)] if index is not None)
    for position in order:
        spare -= try_take(rows[slot_for[position]], beats[position], position, spare)
    durations = distribute([row.minimum for row in rows], target)

    known = catalog(beats, "cast", MAX_CHARACTERS)
    places = catalog(beats, "places", MAX_PLACES)
    objects = catalog(beats, "props", MAX_PROPS)
    ids = {kind: f"character-{index}" for index, kind in enumerate(known, 1)}
    locations = {kind: f"location-{index}" for index, kind in enumerate(places, 1)}
    props = {kind: f"prop-{index}" for index, kind in enumerate(objects, 1)}
    characters = [Character(id=ids[kind], name=item.label, role="main" if index == 0 else "supporting",
                            appearance=item.label if not kind.startswith("named:") else "")
                  for index, (kind, item) in enumerate(known.items())]
    setting = next((item.label for kind, item in places.items() if kind != "tree"), next((item.label for item in places.values()), ""))
    bible = StoryBible(setting=setting, visual_style=STYLES[profile.style],
                       continuity_rules="Reuse each character’s established design, and keep props and locations consistent unless the story shows a change.",
                       characters=characters, locations=[Reference(id=locations[kind], name=item.label) for kind, item in places.items()],
                       props=[Reference(id=props[kind], name=item.label) for kind, item in objects.items()])

    scenes, excerpts = [], {}
    seen: list[str] = []
    previous_place: str | None = None
    last_props: list[str] = []
    for index, allocation in enumerate(rows):
        portion = beats[starts[index]:starts[index + 1]]
        anchor = beats[anchors[index]]
        explicit = unique(item.key for beat in portion for item in beat.cast if item.key in ids)
        tokens = {token for beat in portion for token in beat.tokens}
        recalled = None
        if tokens & FEMININE:
            options = [kind for kind in seen + explicit if kind in ("girl", "woman")]
            recalled = options[0] if len(set(options)) == 1 else None
        elif tokens & MASCULINE:
            options = [kind for kind in seen + explicit if kind in ("boy", "man")]
            recalled = options[0] if len(set(options)) == 1 else None
        if recalled is None and tokens & (FEMININE | MASCULINE | {"वह", "उसने", "সে", "তিনি"}) and len(seen) == 1:
            recalled = seen[0]  # only one previously introduced candidate
        people = unique(([recalled] if recalled else []) + explicit)
        seen = unique(seen + people)

        candidate_places = [item.key for beat in portion for item in beat.places if item.key in places]
        place = next((item.key for item in reversed(anchor.places) if item.key in places), None)
        place = place or (candidate_places[-1] if candidate_places else previous_place)
        previous_place = place
        environment = places[place].label if place else ""
        objects_here = unique(item.key for beat in portion for item in beat.props if item.key in objects)
        if not objects_here and tokens & {"its", "it"} and len(last_props) == 1 and tokens & {"light", "glow", "holds", "carries"}:
            objects_here = last_props
        last_props = objects_here
        moods = {mood for beat in portion for mood in beat.moods}
        emotion = next((label for cue, label in (("concern", "Concern"), ("relief", "Relief"), ("joy", "Joy"),
                                                ("sadness", "Sadness"), ("curiosity", "Curiosity"), ("wonder", "Wonder")) if cue in moods), "")
        opening = index == 0
        final = index == count - 1
        if final and "wonder" in moods and "concern" not in moods:
            emotion = "Wonder"
        headline = (objects[objects_here[0]].label if objects_here and (opening or final) else
                    environment if environment and "concern" in moods else
                    clip(anchor.narration or anchor.source, 58))
        if final:
            camera = "Wide reveal; ease into a slow pull back."
        elif opening:
            camera = "Wide establishing frame; slow push toward the subject."
        elif "concern" in moods:
            camera = "Medium close-up; hold on the reaction, then reveal the obstacle."
        else:
            camera = "Medium portrait frame; gentle pan toward the action."
        animation = MOVEMENT[profile.animation]
        if moods & {"wonder"} and place in ("tree", "forest", "garden"):
            animation += " If illustrated, keep the light effects soft and add a few drifting motes."
        sounds = {"forest": "Soft woodland ambience; subtle footsteps if needed.", "tree": "Leaves and a little forest room tone.",
                  "water": "Quiet water ambience.", "shore": "Gentle surf ambience.", "village": "Low village ambience."}.get(place, "Room tone or silence; choose during audio editing.")
        selection = [beats[position] for position in sorted(allocation.indexes)]
        dialogue = []
        for beat in selection:
            for line in beat.dialogue:
                speaker = recalled if key(line.speaker) in PRONOUNS and recalled else name_key(line.speaker)
                dialogue.append(DialogueLine(character_id=ids.get(speaker), speaker=line.speaker if speaker not in ids else "", text=line.text))
        scene_id = f"scene-{index + 1}"
        scenes.append(Scene(id=scene_id, title=headline or f"Scene {index + 1}", duration_seconds=durations[index],
                            narration=" ".join(beat.narration for beat in selection if beat.narration), dialogue=dialogue,
                            cast=[Appearance(character_id=ids[kind], emotion=emotion) for kind in people],
                            location_id=locations.get(place or ""), environment=environment, prop_ids=[props[kind] for kind in objects_here],
                            visual_description=clip(anchor.source, 1050), camera=camera, animation=animation, sound_effects=sounds,
                            transition="fade_to_black" if final else "dissolve" if opening else "cut"))
        excerpts[scene_id] = clip(" ".join(beat.source for beat in portion), 1100)
    return PlanDocument(analysis=arc_for(beats, conflict, climax), bible=bible, scenes=scenes), PlanSource(
        script_hint=script_hint(story), story_words=len(words(story)), source_beats=length,
        spoken_beats=sum(len(row.indexes) for row in rows), excerpts=excerpts)
