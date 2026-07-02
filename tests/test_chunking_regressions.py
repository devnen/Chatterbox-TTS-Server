"""Regression tests for text chunking behavior in utils.chunk_text_by_sentences.

Add new cases by appending to CHUNK_COUNT_CASES with:
- id: short stable label for subTest output
- text: input text to chunk
- chunk_size: max chunk character budget
- expected_chunks: expected number of chunks
"""

from dataclasses import dataclass
from typing import Optional
import unittest
from unittest.mock import patch

from msgpack import fallback
from sympy import false
from utils import chunk_text_by_sentences, config_manager


@dataclass(frozen=True)
class ChunkCountCase:
    id: str
    text: str
    chunk_size: int
    expected_chunks: int
    fallback_enabled: Optional[bool] = None
    hard_limit_factor: Optional[float] = None


CHUNK_COUNT_CASES = [
    ChunkCountCase(
        id="divider_stars_separates_paragraphs",
        text=(
            "Intro line\n"
            "* * * * *\n"
            "This is after divider and should not glue everything forever. Another sentence.\n\n"
            "Tail paragraph."
        ),
        chunk_size=40,
        expected_chunks=3,
    ),
    ChunkCountCase(
        id="divider_with_sparse_punctuation_default_off",
        text=(
            "Alpha beta gamma delta epsilon zeta eta theta\n"
            "* * * * *\n"
            "Iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega"
        ),
        chunk_size=35,
        expected_chunks=2,
    ),
    ChunkCountCase(
        id="divider_with_sparse_punctuation_fallback_enabled_factor_1",
        text=(
            "Alpha beta gamma delta epsilon zeta eta theta\n"
            "* * * * *\n"
            "Iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega"
        ),
        chunk_size=35,
        expected_chunks=5,
        fallback_enabled=True,
        hard_limit_factor=1.0,
    ),
    ChunkCountCase(
        id="narrative_dash_regression_issue_144",
        text="wait that sounds lewd)-\n\nWithin the ruins, we waited.",
        chunk_size=20,
        expected_chunks=2,
    ),
    ChunkCountCase(
        id="bullet_list_behavior_remains_stable",
        text="Shopping list:\n- eggs\n- milk\n- butter\nDone.",
        chunk_size=30,
        expected_chunks=2,
    ),
    ChunkCountCase(
        id="non_positive_chunk_size_returns_single_chunk",
        text="One. Two. Three.",
        chunk_size=0,
        expected_chunks=1,
    ),
    ChunkCountCase(
        id="single_long_sentence_factor_4_splits_at_4x_chunk_size",
        text=(
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
            "omicron pi rho sigma tau upsilon phi chi psi omega alpha beta gamma delta "
            "epsilon zeta eta theta iota"
        ),
        chunk_size=40,
        expected_chunks=2,
        fallback_enabled=True,
        hard_limit_factor=4.0,
    ),
    ChunkCountCase(
        id="Original example text with five star issue",
        text=("""Note also that this fic has my characters having strong opinions about Cerberus and the Citadel Council. Some of those opinions are actually shared by the author. Some are not, but my characters would believe them anyway. And some things in this fic are drawn directly from canon, and some other things absolutely are not. So vigorous canon nitpicking is neither necessary nor desired – just assume the author already knows most of it and wrote the story their way anyway. This is a fanfic, after all.

* * * * *
​

Mindoir
11 MAY 2170

Even in the interstellar future, people still needed to eat. And that meant farmers still grew food, even if the tractors were VI-piloted drones and ran on ultra-high-density batteries charged from the farm's element-zero reactor.

A tall redheaded teenaged girl with a smear of dirt on her cheek straightened up from where she'd been lying underneath one of the drone-tractors where it had stalled out in the fields, stretched luxuriously to work the kinks out of her back, and brought one wrist up to her mouth. The omni-tool mounted there flared into visibility as she spoke.

"Intercom, local. Dad? I've fixed tractor three, should I have it resume program?" she asked.

"All right then." He nodded. "So, you agree that we should change the schedule? Take the next step now?"

"Yes." His wife nodded. "I think that she's old enough to handle it. And I also think that the longer we wait to tell her, the less likely she'd be to accept it."

"… I'll make the call." Michael Shepard reluctantly agreed.

* * * * *
​
"Wake up!" The urgent female voice brought Jane out of a sound sleep."""),
        chunk_size=240,
        expected_chunks=8,
    ),
    ChunkCountCase(
        id="Original text with dash issue",
        text=""""KNOCK KNOCK MOTHERFUCKERS, WHO ORDERED A BEATING?" 
  Several blocks away, Lady Photon paused in the middle of shaping her force fields into a corral and tilted her head. "Did you hear something?""Nope," Glory Girl shamelessly lied. "I've no idea what you're talking about."  The reaction time for your average human is 0.25 seconds. A quarter of a second for your eyes to see something, report back to your brain, and your brain to decide what to do about it.That time can be stretched surprisingly far when your brain keeps going wait, no, it's a what?' to your eyes instead of doing its job.I burst into the factory yard, angry electric guitars screaming in my loudspeakers. My comms detected an active security network - I set my EWF package on it and every single active camera feed in the building dissolved into useless static, motion sensors firing randomly.
 FADING, FALLING, LOST IN FOREVER - 
ABB gangers moved as if in slow motion, still reeling from the explosions - explosions going across the compound because if I  could  task my AI drones with setting off every safe' charge they could find, why the fuck not, let Bakuda think we were coming from all directions at once. My tactical network sung in the back of my head, a constant stream of data. Lifesigns collated with weapon-shapes, threat assessment, detected charges, estimated yields and areas-of-effect, target priorities - a thousand different things, my accelerated mind hyperaware of every single one of them. 
 Phluub! 
In one of the second-floor rooms hastily converted into an armory, several ABB gangers were in the process of grabbing and loading weapons. My snare grenade arced through the air and smashed through the window. A heartbeat later, tendrils of whipping foaming snare compound burst out of the jagged hole.
 Overload. Airburst. 

 ###LOADING 
There was a ratcheting  clunk  as the autoloader in my belly switched drums and loaded in another grenade.
 Phluub! Phluub! 
Overload grenades are like flashbangs, on steroids - the concussive stunning explosion paired with stingballs', painful rubber shrapnel. Two detonations fractions of a second apart from one another shook the pavement, drove stunned and disoriented ABB watchmen out of cover.Threat indicators flickered over my sight. 
 - THE HURRICANE OF MY LIFE - CAN IT BE - 

 Low-caliber pistol, threat negligible - nonaugmented melee weapon, threat null - high-power rifle, threat moderate - disable/neutralize, lethal force restricted -  
Triangular target indicators winked to life on him. My arm came up -
 ShhhzakPOW!  
The Undersiders' contacts came to life behind me, and Tattletale's first shot with her laser pulser caught the coat-clad ganger on the shoulder, detonated in an actinic flash of energized plasma. There was no visible beam, no muzzle flash, barely a noise from the actual gun - the Undersiders pointed their pulsers, and two near-simultaneous laser pulses flashed on every trigger pull. The first flash-vaporized a minute amount of material on the target point, barely enough on bare skin to qualify as sunburn, converted the flash-burned material into plasma - the second energized the plasma and detonated it with a bright flash of UV-white, a loud rippling  crack!  and a concussive shockwave, blinding, disorienting, stunning. The Undersiders moved up with me, blurred ghosts in chameleon-mode crashsuits, white-purple eruptions of light and noise where they pointed, while I thundered into the compound, scattered panicked return fire pinging and spanging harmlessly off my armored carapace.It turned out it was  really  hard to effectively shoot at something when you didn't quite believe your target was there in the first place. Even more so when the target was blasting angry heavy metal at you at volumes that vibrated plaster off walls and actually made your eyeballs throb in their sockets.
 - I STAND AND FIGHT - I'M NOT AFRAID TO DIE - 
  "Hold them back!"Shielder's shining blue force fields sprung to life, sculpted themselves into fences and barriers pushing against the mass of oncoming humanity. Gunshots and screams rang in the air, mixed with the awful rattling  thump  of distant explosions.Victoria had fought the E88 before, and most of the time - the Nazis were loud and postured a lot, but show them actual threat and they'd back down. Most of the time. Now, though - they were out for blood. New Wave'd had to pound a whole squad of them before the others started faltering.Then the ABB came in, and these weren't the hardened gangers they'd expected. Some among the mass bore gang colors, sure, armbands or bandanas or coats of red and green, but most of them - were just  people, people driven on by terror and given weapons pointed their way. """,
        chunk_size=240,
        expected_chunks=23,
    ),
]


def print_list_make_chunks_obvious(lst: list) -> str:
    result = "["
    for element in lst:
        result += "\n" + str(element) + "|||"
    return result + "]"


class TestChunkTextBySentencesRegressions(unittest.TestCase):

    def test_chunk_count_regressions(self) -> None:
        for case in CHUNK_COUNT_CASES:
            with self.subTest(case=case.id):
                def _mock_get_bool(key_path: str, default: Optional[bool] = None) -> bool:
                    if (
                        key_path == "text_chunking.enable_hard_limit_fallback"
                        and case.fallback_enabled is not None
                    ):
                        return case.fallback_enabled
                    return default if default is not None else False

                def _mock_get_float(
                    key_path: str, default: Optional[float] = None
                ) -> float:
                    if (
                        key_path == "text_chunking.hard_limit_factor"
                        and case.hard_limit_factor is not None
                    ):
                        return case.hard_limit_factor
                    return default if default is not None else 0.0

                with patch.object(config_manager, "get_bool", side_effect=_mock_get_bool):
                    with patch.object(
                        config_manager, "get_float", side_effect=_mock_get_float
                    ):
                        chunks = chunk_text_by_sentences(case.text, case.chunk_size)

                self.assertEqual(
                    len(chunks),
                    case.expected_chunks,
                    msg=(
                        f"Case '{case.id}' expected {case.expected_chunks} chunks "
                        f"but got {len(chunks)}: {print_list_make_chunks_obvious(chunks)}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()



