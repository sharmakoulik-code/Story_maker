from pathlib import Path

from .character_store import CharacterStore
from .plan_models import CharacterDesign, LibraryPin, SavePlan
from .plan_store import PlanStore
from .schemas import Draft, DraftProfile
from .storage import Workspace
from .storyboard import StoryboardStore
from .visual_models import Credits, ReviewTarget, ShotReview

BLUE_FLOWER = ("A little chibi girl finds a glowing blue flower in a mysterious forest. She follows its light and "
               "discovers a tiny magical creature trapped beneath an old tree. She helps the creature, and together "
               "they watch the forest become illuminated with magical lights.")
ART = Path(__file__).with_name("demo_art")
CREDITS = Credits(source="Koma Studio original demo artwork", license_note="CC0-1.0")


def seed_preview(workspace: Workspace, plans: PlanStore, characters: CharacterStore, board: StoryboardStore) -> None:
    """Examples for the isolated development preview, never the Windows library."""
    if workspace.list_projects():
        return
    drafts = [
        Draft(title="A Letter from the Tide", profile=DraftProfile(style="moonlit", duration_seconds=90),
              story="One night, a paper boat washes up on the shore. Inside is a letter from someone the village has almost forgotten. An apprentice boatmaker follows a trail of moonlit tide pools to deliver a reply."),
        Draft(title="Across the Violet Pass", profile=DraftProfile(style="cel", duration_seconds=60),
              story="A young courier climbs the violet pass with a bundle of letters as the last train whistles below. At the summit, she meets a fox guarding a forgotten station and learns that one letter has been waiting for a hundred years."),
        Draft(title="Lanterns After Dusk", profile=DraftProfile(style="storybook", duration_seconds=30),
              story="When the village lanterns go out, a little traveler carries the last flame through the woods. A shy spirit shows her how to share its light without letting it fade."),
    ]
    for draft in drafts:
        project = workspace.create_project(draft)
        if draft.title == "Lanterns After Dusk":
            plans.generate(project.id, expected=None)

    if (ART / "flower.webp").is_file():
        seed_blue_flower(workspace, plans, characters, board)


def seed_blue_flower(workspace: Workspace, plans: PlanStore, characters: CharacterStore, board: StoryboardStore) -> None:
    project = workspace.create_project(Draft(title="The Blue Flower", story=BLUE_FLOWER, profile=DraftProfile(duration_seconds=30)))
    plan = plans.generate(project.id, expected=None).plan
    assert plan is not None
    designs = [
        (CharacterDesign(name="Mina · forest traveler", description="A small traveler drawn to the blue flower.",
                         face="Soft round cheeks; lightly flushed", body="Chibi proportions with short boots",
                         hair="Plum bob with a sweeping fringe", eyes="Large teal eyes", clothing="Mint cape and rose scarf",
                         accessories="Small gold star pin", generation_notes="Keep the cape and star pin consistent across angles."),
         "traveler-reference.webp"),
        (CharacterDesign(name="Pip · woodland spirit", description="Fox-like forest creature with a glowing forehead.",
                         body="Tiny plush proportions", face="Cream muzzle and little round eyes", eyes="Deep plum",
                         accessories="Amber diamond-shaped glow", generation_notes="Keep the pale tail tip and short ears."),
         "creature-reference.webp"),
    ]
    for cast_entry, (design, filename) in zip(plan.document.bible.characters, designs, strict=True):
        item = characters.create(design)
        with (ART / filename).open("rb") as stream:
            item = characters.import_reference(item.id, item.revision, stream, filename, CREDITS)
        assert item.reference is not None
        # Keep the story's cast IDs and names; pin the design and a specific saved image.
        for field, value in design.model_dump(exclude={"name"}).items():
            setattr(cast_entry, field, value)
        cast_entry.library_pin = LibraryPin(character_id=item.id, image_id=item.reference.id)
    changed = plans.save(project.id, SavePlan(revision=plan.revision, document=plan.document)).plan
    assert changed is not None
    approved = plans.approve(project.id, changed.revision, True).plan
    assert approved is not None
    for scene, filename in zip(approved.document.scenes, ("flower.webp", "old-tree-study.webp", "forest-lights.webp"), strict=True):
        with (ART / filename).open("rb") as stream:
            board.import_frame(project.id, scene.id, approved.revision, 0, stream, filename, CREDITS)
    current = board.view(project.id)
    reviewed = board.review(project.id, ShotReview(plan_revision=approved.revision, approved=True,
        targets=[ReviewTarget(scene_id=shot.scene_id, revision=shot.revision) for shot in current.shots]))
    middle = reviewed.shots[1]
    with (ART / "old-tree.webp").open("rb") as stream:
        board.import_frame(project.id, middle.scene_id, approved.revision, middle.revision, stream, "old-tree.webp", CREDITS)
