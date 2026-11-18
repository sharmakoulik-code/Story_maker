"""Script timing and automatic prompt construction. These are not audio measurements."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .plan_models import MIN_GENERATED_SCENE, PlanDocument, PlanTiming, Reference, Scene, SceneTiming, StoryBible
from .schemas import DraftProfile
from .story_text import clip, script_hint, words

RATES = {"en": 120, "hi": 108, "bn": 104}
SCRIPTS = {"en": "Latin", "hi": "Devanagari", "bn": "Bengali"}
SCENE_PAD_MS = 650
TURN_PAD_MS = 320
CLAUSE = re.compile(r"[,;:—]")
STOP = re.compile(r"[.!?…।॥。]+")


@dataclass(frozen=True)
class Cost:
    words: int = 0
    ms: int = 0

    def __add__(self, other: Cost) -> Cost:
        return Cost(self.words + other.words, self.ms + other.ms)


def planning_rate(text: str, language: str) -> int:
    rate = RATES[language]
    for char in text:
        if 0x0980 <= ord(char) <= 0x09FF and char.isalpha():
            return min(rate, RATES["bn"])
        if 0x0900 <= ord(char) <= 0x097F and char.isalpha():
            rate = min(rate, RATES["hi"])
    return rate


def spoken_text(document: PlanDocument) -> str:
    return " ".join(line for scene in document.scenes for line in [scene.narration, *(item.text for item in scene.dialogue)])


def read_cost(text: str, rate: int) -> Cost:
    units = words(text)
    if not units:
        return Cost()
    # Allow some extra time for long words or number/initial strings. This is deliberately conservative.
    weighted = sum(1 + max(0, (sum(char.isalnum() for char in token) - 1) // 12) for token in units)
    return Cost(len(units), math.ceil(weighted * 60_000 / rate) + 160 * len(CLAUSE.findall(text)) + 300 * len(STOP.findall(text)))


def with_scene_padding(narration: Cost, dialogue: Cost, spoken_dialogue_lines: int) -> Cost:
    turns = bool(narration.words) + spoken_dialogue_lines
    if not turns:
        return Cost()
    return Cost(narration.words + dialogue.words,
                narration.ms + dialogue.ms + SCENE_PAD_MS + (turns - 1) * TURN_PAD_MS)


def scene_cost(scene: Scene, rate: int) -> Cost:
    spoken = [read_cost(line.text, rate) for line in scene.dialogue]
    dialogue = sum(spoken, Cost())
    return with_scene_padding(read_cost(scene.narration, rate), dialogue, sum(bool(item.words) for item in spoken))


def distribute(floors: list[int], target: int) -> list[int]:
    slack = target - sum(floors)
    if not floors or slack < 0:
        raise ValueError("Scene durations cannot fit the target.")
    each, remainder = divmod(slack, len(floors))
    return [floor + each + (index < remainder) for index, floor in enumerate(floors)]


def fit_durations(document: PlanDocument, profile: DraftProfile) -> PlanDocument:
    rate = planning_rate(spoken_text(document), profile.language)
    minimums = [max(1, math.ceil(scene_cost(scene, rate).ms / 1000)) for scene in document.scenes]
    target = profile.duration_seconds
    if sum(minimums) > target:
        raise ValueError(f"These scenes need at least {sum(minimums)} seconds at the planning pace. Shorten the script or use a longer target. The saved plan was not changed.")
    padded = [max(MIN_GENERATED_SCENE, floor) for floor in minimums]
    durations = distribute(padded if sum(padded) <= target else minimums, target)
    return document.model_copy(update={"scenes": [scene.model_copy(update={"duration_seconds": duration})
                                                 for scene, duration in zip(document.scenes, durations, strict=True)]})


def reference_text(reference: Reference, limit: int) -> str:
    return f"{reference.name} ({clip(reference.description, limit)})" if reference.description else reference.name


def image_prompt(bible: StoryBible, scene: Scene) -> str:
    if scene.image_prompt_override:
        return scene.image_prompt_override
    characters = {item.id: item for item in bible.characters}
    props = {item.id: item for item in bible.props}
    locations = {item.id: item for item in bible.locations}
    people = []
    for appearance in scene.cast:
        item = characters[appearance.character_id]
        cues = (("face", item.face), ("body", item.body), ("clothing", item.clothing), ("hair", item.hair),
                ("eyes", item.eyes), ("accessories", item.accessories), ("expression", appearance.emotion),
                ("design instructions", item.generation_notes))
        description = "; ".join(part for part in [clip(item.appearance or item.description, 120),
                                                   *(f"{label}: {clip(value, 80)}" for label, value in cues if value)] if part)
        people.append(f"{item.name}: {clip(description, 650)}" if description else item.name)
    place = locations.get(scene.location_id or "")
    environment = [clip(bible.setting, 180)] if bible.setting and (not place or bible.setting != place.name) else []
    if place:
        environment.append(reference_text(place, 240))
    if scene.environment and (not place or scene.environment != place.name):
        environment.append(clip(scene.environment, 200))
    sections = [bible.visual_style or "Anime-inspired 2D illustration", "Portrait 9:16 composition; soft cinematic lighting and readable silhouettes",
                f"Environment: {'; '.join(dict.fromkeys(environment))}" if environment else "",
                f"Scene action: {clip(scene.visual_description, 600)}" if scene.visual_description else "",
                f"Cast: {' | '.join(people)}" if people else "",
                f"Key props: {' | '.join(reference_text(props[key], 140) for key in scene.prop_ids)}" if scene.prop_ids else "",
                f"Framing: {clip(scene.camera, 350)}" if scene.camera else "",
                f"Continuity: {clip(bible.continuity_rules, 450)}" if bible.continuity_rules else ""]
    return clip(". ".join(section.rstrip(". ") for section in sections if section) + ".", 8000)


def timing_for(document: PlanDocument, profile: DraftProfile) -> PlanTiming:
    text = spoken_text(document)
    target, rate = profile.duration_seconds, planning_rate(text, profile.language)
    issues, cautions, measurements = [], [], []
    started, all_words = 0, 0
    silent, long_holds = [], []
    for number, scene in enumerate(document.scenes, 1):
        cost = scene_cost(scene, rate)
        minimum = math.ceil(cost.ms / 1000)
        end = started + scene.duration_seconds
        fits = minimum <= scene.duration_seconds
        if not fits:
            issues.append(f"Scene {number} needs at least {minimum}s for the script; only {scene.duration_seconds}s is assigned.")
        if not cost.words:
            silent.append(str(number))
        if scene.duration_seconds > max(16, minimum + 9):
            long_holds.append(str(number))
        measurements.append(SceneTiming(scene_id=scene.id, number=number, start_seconds=started, end_seconds=end,
                                        spoken_words=cost.words, speech_seconds=math.ceil(cost.ms / 100) / 10,
                                        minimum_seconds=minimum, fits=fits, image_prompt=image_prompt(document.bible, scene)))
        started, all_words = end, all_words + cost.words
    if started != target:
        issues.append(f"Scenes total {started}s; the saved target is {target}s. Adjust the durations or use Fit to target.")
    if not all_words:
        issues.append("No narration or dialogue could fit. Add a short spoken line before approving the plan.")
    if silent and all_words:
        cautions.append(f"No spoken lines in scene(s) {', '.join(silent)}. Keep them as visual beats or add narration.")
    if long_holds:
        cautions.append(f"Long visual holds in scene(s) {', '.join(long_holds)}. Consider adding story beats or choosing a shorter target.")
    script = script_hint(text)
    if script not in (SCRIPTS[profile.language], "unknown"):
        cautions.append(f"Planned speech uses {script} text, which might not match the selected narration language. This planner does not translate; review the script before recording.")
    return PlanTiming(target_seconds=target, planned_seconds=started, words_per_minute=rate, spoken_words=all_words,
                      scenes=measurements, issues=issues, cautions=cautions, can_approve=not issues)
