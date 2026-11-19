"""Original, separable Blue Flower art. Write one transparent SVG per native 2× sprite."""
import random
import sys
from pathlib import Path

from draw_preview import DEFS, light, woods, motes


TORSO = '''
<path d="M57 262q28 6 32 22l-4 18q1 13-13 15H49q-11 0-10-8 2-10 14-14Z M101 271q16-11 30-8l8 31q17 4 17 14 0 9-16 9h-21q-12-2-12-15Z" fill="#483a58" stroke="#252c42" stroke-width="3"/>
<path d="M59 299l17-1m48-1 16 1" stroke="#d6acaa" stroke-width="3" stroke-linecap="round"/>
<path d="M57 164q30 5 69-2 23 13 28 36l9 38 20 46q-27 23-65 13-32 12-59 0-20 3-40-14l17-44q2-40 21-73Z" fill="url(#cape)" stroke="#41666c" stroke-width="3"/>
<path d="M48 194Q26 212 9 230l12 15q19-9 36-42Z" fill="url(#cape)" stroke="#41666c" stroke-width="2.6"/>
<path d="M81 200q-19 58-24 84m67-82q7 49 22 80m-44-50-6 59" fill="none" stroke="#cce5bb" stroke-width="2.3" opacity=".47"/>
<path d="M22 274q29 16 51 12 42 14 103-12" fill="none" stroke="#dbdca5" stroke-width="2.8" opacity=".83"/>
<path d="M48 161q32 19 85-2l9 16q-39 28-90 6Z" fill="#c98d87" stroke="#805e72" stroke-width="2.7"/>
<path d="M118 175q7 25 20 45l-15 5-18-45" fill="#db9b88" stroke="#926c78" stroke-width="2"/>
<circle cx="94" cy="184" r="5" fill="#c8f0db" stroke="#57776d" stroke-width="1.6"/>
'''
FACE = '''
<path d="M44 161q-25-17-26-50-2-39 25-65 43-46 97-15 35 23 40 68 8 39-12 69l-12 17-124-9q18-9 12-15Z" fill="url(#hair)" stroke="#44394e" stroke-width="3"/>
<ellipse cx="88" cy="115" rx="64" ry="59" fill="url(#skin)" stroke="#8c606c" stroke-width="2.4"/>
<ellipse cx="27" cy="134" rx="8" ry="10" fill="#efb9a2"/><ellipse cx="149" cy="132" rx="8" ry="10" fill="#efb9a2"/>
<ellipse cx="43" cy="145" rx="12" ry="4.6" fill="#dc7a8c" opacity=".48"/><ellipse cx="130" cy="145" rx="12" ry="4.6" fill="#dc7a8c" opacity=".48"/>
<path d="m89 138 3 2" fill="none" stroke="#9d626d" stroke-linecap="round" stroke-width="2"/>
'''
FRINGE = '''
<path d="M29 126Q12 94 34 60q21-35 61-35 49-2 68 36 14 27-13 71l-7-29q-5-7-14-14l-7 20q-4-20-21-38-10 34-38 41l7-21q-16 16-41 35Z" fill="url(#hair)" stroke="#554158" stroke-width="2.5"/>
<path d="M30 94Q50 46 103 44q46 2 57 34M39 91q21-41 65-40q28 0 44 16" stroke="#c4a1ad" stroke-width="2.5" fill="none" opacity=".66" stroke-linecap="round"/>
<path d="M24 123q10 28 4 45 20-9 26-31m86-17q-4 34 12 48 16-15 20-48" fill="url(#hair)" stroke="#57445b" stroke-width="2"/>
<path d="M137 78l6 6-2 8-8-3-4-7 8-4Z" fill="#fff1b2" stroke="#b99579" stroke-width="1.7"/><circle cx="151" cy="96" r="3.7" fill="#f1dab0"/>
'''
EYES = '''
<path d="M42 121q9-16 21-9 9 6 9 22-11 14-23 7-10-6-7-20Zm62 0q10-17 23-7 10 8 7 24-14 9-25 2-8-6-5-19Z" fill="#fff9e8"/>
<ellipse cx="57" cy="128" rx="10.5" ry="15.4" fill="url(#iris)"/><ellipse cx="122" cy="128" rx="10.5" ry="15.4" fill="url(#iris)"/>
<ellipse cx="59" cy="126" rx="5.8" ry="9" fill="#283449"/><ellipse cx="124" cy="126" rx="5.8" ry="9" fill="#283449"/>
<path d="M36 117q8 5 11 0 12-13 23 2m28-2q6 1 10-3 16-12 28 5" fill="none" stroke="#3a2b40" stroke-width="3" stroke-linecap="round"/>
<g fill="#fffdf3"><circle cx="54" cy="121" r="4"/><circle cx="117" cy="121" r="4"/><circle cx="62" cy="133" r="1.6"/><circle cx="127" cy="133" r="1.6"/></g>
'''
PETALS = ''.join(f'''<g transform="rotate({angle})"><path d="M0 3Q-32-18-18-44 2-53 16-28 24-10 0 3Z" fill="url(#petal)" stroke="#aeefff" stroke-width="1.1"/>
<path d="M0-9Q-7-25 1-43M1-17Q5-27 6-32M-4-21l-5-10" fill="none" stroke="#e3ffff" stroke-width=".8" opacity=".61"/></g>''' for angle in (0, 72, 144, 216, 288))


def write_art(dest):
    dest.mkdir(parents=True, exist_ok=True)
    mid, deep, woods_svg = woods(0)
    defs = DEFS.replace('MID', mid).replace('DEEP', deep)

    def svg(name, box, content):
        x, y, w, h = box
        (dest / f'bf-{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w*2}" height="{h*2}" viewBox="{x} {y} {w} {h}"><defs>{defs}</defs><g stroke-linejoin="round">{content}</g></svg>', encoding='utf-8')

    ground = '''<path d="M0 726Q146 668 229 747T540 690V960H0Z" fill="#152f3c" opacity=".8"/>
<path d="M277 604c-69 47-48 85 15 125 64 41 49 78-7 102-46 19-130 33-159 129h286c-26-69-26-127 13-166 36-36-22-94-85-116-49-17-73-25-48-81Z" fill="url(#path)" opacity=".72"/>
<path d="M0 39Q112 89 161 9L18 0Z M531 6Q399 76 323 29Q424 0 540 0Z" fill="#172b3e"/>
<path d="M429 0q-58 208-248 718h103Q404 472 464 0Z" fill="#a4cbbc" opacity=".085"/>'''
    rng = random.Random(659)
    details = []
    for _ in range(92):
        x,y = rng.randrange(540), rng.randrange(599, 959)
        rx = rng.uniform(1.5, 8) * (y-500)/450
        details.append(f'<ellipse cx="{x}" cy="{y}" rx="{rx:.2f}" ry="{rx*.43:.2f}" fill="{rng.choice(("#547469", "#466d71", "#304853", "#7c877a"))}" opacity=".57"/>')
    for x, y, size, flip in [(89,736,.58,1),(433,748,.62,-1),(471,802,.88,-1),(163,625,.42,1),(38,814,.79,1),(522,701,.56,-1)]:
        details.append(fern(x,y,size,flip))
    svg('forest', (0,0,540,960), woods_svg + ground + ''.join(details) + motes(0) + '<rect width="540" height="960" fill="url(#edge)"/>')
    svg('foreground', (0,728,540,232), fern(9,965,1.85,1)+fern(532,974,2.19,-1)+fern(473,977,1.13,-1)+fern(68,974,.97,1))
    bokeh = []
    for _ in range(37):
        x, y, r = rng.randrange(540), rng.randrange(960), rng.randint(12,94)
        bokeh.append(light(x,y,r,rng.choice(('cyan','wash','gold')),rng.uniform(.08,.35)))
    svg('glade-detail', (0,0,540,960), '<rect width="540" height="960" fill="#10182a"/><g transform="translate(-220,-215) scale(1.84)" opacity=".65" filter="url(#fog)">' + woods_svg + '</g>' + ''.join(bokeh) + light(265,452,345,'cyan',.53) + '<rect width="540" height="960" fill="url(#edge)"/>')
    svg('shadow', (0,297,194,35), '<ellipse cx="97" cy="314" rx="96" ry="16" fill="#090f21" opacity=".64"/>')
    svg('torso', (4,154,184,170), TORSO)
    svg('face', (12,16,179,171), FACE)
    svg('fringe', (12,18,179,155), FRINGE)
    svg('eyes', (32,108,108,38), EYES)
    svg('lids', (32,108,108,38), '<path d="M38 126q16 14 34 0m31-1q15 15 31 0M38 126l-4-2m100 1 4-2" stroke="#533548" stroke-width="2.8" stroke-linecap="round" fill="none"/>')
    svg('brows', (44,90,94,17), '<path d="M49 98q14-10 27 1m30-1q15-9 27 1" stroke="#674456" stroke-width="2.8" fill="none" stroke-linecap="round"/>')
    svg('smile', (78,144,25,19), '<path d="M83 151q7 5 14-2" fill="none" stroke="#9d626d" stroke-linecap="round" stroke-width="2"/>')
    svg('mouth', (78,144,25,19), '<path d="M85 150q6-7 12-1 4 7-5 10-9 0-7-9Z" fill="#9f576c" stroke="#7c4e62" stroke-width="1.3"/><path d="M87 154q7-2 10 0-3 5-7 4Z" fill="#ef9a9e"/>')
    svg('sleeve', (-14,-10,66,44), '<path d="M-5-7Q2-12 14-4q13 8 33 12l-3 21q-24-3-42-15-21-12-7-21Z" fill="url(#cape)" stroke="#41666c" stroke-width="2.6"/><path d="M36 7l-5 20 13 2 4-20Zm-31-9q10 5 19 12" fill="#b6d0a6" stroke="#678a81" stroke-width="1.8"/>')
    svg('hand', (-5,-13,34,29), '<path d="M-3-3Q6-9 13-8l9-3q8 0 4 5l-7 4 5 2q4 9-11 12L-4 8Z" fill="url(#skin)" stroke="#9c6e78" stroke-width="1.8"/><path d="M10 6q5-2 6-5" fill="none" stroke="#b88182" stroke-width="1.1" stroke-linecap="round"/>')
    svg('stem', (-66,-4,108,156), '<path d="M-14 144Q-42 102-1 49 9 24 0-1" fill="none" stroke="#79c3aa" stroke-width="5" stroke-linecap="round"/><path d="M-17 127Q-58 112-57 80-20 85-17 127Zm-4-48Q4 38 32 50q-5 25-53 29Z" fill="#62aa91" stroke="#abd5ac" stroke-width="2"/><path d="M-26 111l-22-24m34-19 37-16" stroke="#c7eed7" fill="none" opacity=".6"/>')
    svg('petals', (-60,-60,120,120), PETALS+'<circle r="14" fill="#dbfbff"/><circle r="6" fill="#fffde0"/>'+light(0,0,60,opacity=.59))
    svg('halo', (-134,-134,268,268), light(0,0,133,opacity=.84))
    svg('spark', (-28,-28,56,56), light(0,0,28,opacity=.85)+'<path d="M-5 0q5-1 5-9 0 8 5 9-5 0-5 9 0-8-5-9Z" fill="#e6ffff"/>')


def fern(x,y,scale,flip):
    fronds = []
    for i in range(6):
        tx = 17 + i*12
        ty = -98 + i*10
        fronds.append(f'<path d="M0 0Q1 -52 {tx} {ty}q-4 23-{tx*.62:.1f} 42 4 7-{tx*.38:.1f} {(-ty-42):.1f}Z" fill="{("#214653", "#386763", "#2f575c", "#28484e", "#48786f", "#31555f")[i]}" stroke="#1b3745" stroke-width="1.1"/>')
        fronds.append(f'<path d="M1-1Q{tx*.48:.2f}-46 {tx} {ty}" fill="none" stroke="#669784" opacity=".45"/>')
    return f'<g transform="translate({x} {y}) scale({scale*flip} {scale})">' + ''.join(fronds) + '</g>'


if __name__ == '__main__':
    write_art(Path(sys.argv[1]))
