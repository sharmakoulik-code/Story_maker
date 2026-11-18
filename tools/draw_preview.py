"""Author the Koma demo stills as SVG; no models, fonts, or network calls.

The scenes and reference sheets share the same character design. The browser is only used as an
SVG rasterizer when rebuilding the preview art, not during normal app use.
"""
import random
import sys
from pathlib import Path


DEFS = '''
<radialGradient id="bg" cx="52%" cy="44%" r="64%"><stop stop-color="MID"/><stop offset=".5" stop-color="DEEP"/><stop offset="1" stop-color="#0a1425"/></radialGradient>
<radialGradient id="cyan"><stop stop-color="#edffff" stop-opacity=".92"/><stop offset=".14" stop-color="#8eeeff" stop-opacity=".62"/><stop offset=".46" stop-color="#42acd7" stop-opacity=".26"/><stop offset="1" stop-color="#237399" stop-opacity="0"/></radialGradient>
<radialGradient id="gold"><stop stop-color="#fff9bd" stop-opacity=".95"/><stop offset=".2" stop-color="#ffd990" stop-opacity=".58"/><stop offset=".52" stop-color="#fdaf64" stop-opacity=".28"/><stop offset="1" stop-color="#ee8976" stop-opacity="0"/></radialGradient>
<radialGradient id="wash"><stop stop-color="#7ee2c7" stop-opacity=".48"/><stop offset=".47" stop-color="#578e99" stop-opacity=".27"/><stop offset="1" stop-color="#577999" stop-opacity="0"/></radialGradient>
<radialGradient id="edge"><stop offset=".4" stop-color="#151c32" stop-opacity="0"/><stop offset="1" stop-color="#080b18" stop-opacity=".69"/></radialGradient>
<linearGradient id="path" x2=".23" y2="1"><stop stop-color="#91ab92" stop-opacity=".47"/><stop offset="1" stop-color="#325349" stop-opacity=".19"/></linearGradient>
<linearGradient id="bark"><stop stop-color="#4e5862"/><stop offset=".32" stop-color="#37444d"/><stop offset="1" stop-color="#202536"/></linearGradient>
<linearGradient id="iris" x2="0" y2="1"><stop stop-color="#283847"/><stop offset=".54" stop-color="#3c7b83"/><stop offset="1" stop-color="#adfbe0"/></linearGradient>
<linearGradient id="cape" x2=".78" y2="1"><stop stop-color="#c9e1b4"/><stop offset=".37" stop-color="#78b69e"/><stop offset=".75" stop-color="#478b88"/><stop offset="1" stop-color="#365971"/></linearGradient>
<linearGradient id="skin" x2=".22" y2="1"><stop stop-color="#fff0cb"/><stop offset=".68" stop-color="#f8c8aa"/><stop offset="1" stop-color="#e9a797"/></linearGradient>
<linearGradient id="hair" x2=".25" y2="1"><stop stop-color="#9c799b"/><stop offset=".46" stop-color="#5d475e"/><stop offset="1" stop-color="#30283e"/></linearGradient>
<linearGradient id="fox" x2=".18" y2="1"><stop stop-color="#ffe8a0"/><stop offset=".6" stop-color="#edb078"/><stop offset="1" stop-color="#bf7773"/></linearGradient>
<linearGradient id="petal" x2="0" y2="1"><stop stop-color="#e8feff"/><stop offset=".43" stop-color="#8eeaff"/><stop offset="1" stop-color="#4988e1"/></linearGradient>
<filter id="fog"><feGaussianBlur stdDeviation="13"/></filter>
<filter id="paper"><feTurbulence baseFrequency=".41" numOctaves="3" seed="13" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter>
'''


def light(x, y, r, color="cyan", opacity=1, yr=None):
    return f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{yr or r}" fill="url(#{color})" opacity="{opacity}"/>'


def girl(x, y, scale, back=False):
    eyes = '' if back else '''
    <path d="M49 98q14-10 27 1m30-1q15-9 27 1" stroke="#674456" stroke-width="2.8" fill="none" stroke-linecap="round"/>
    <path d="M42 121q9-16 21-9 9 6 9 22-11 14-23 7-10-6-7-20Zm62 0q10-17 23-7 10 8 7 24-14 9-25 2-8-6-5-19Z" fill="#fff9e8"/>
    <ellipse cx="57" cy="128" rx="10.5" ry="15.4" fill="url(#iris)"/><ellipse cx="122" cy="128" rx="10.5" ry="15.4" fill="url(#iris)"/>
    <ellipse cx="59" cy="126" rx="5.8" ry="9" fill="#283449"/><ellipse cx="124" cy="126" rx="5.8" ry="9" fill="#283449"/>
    <path d="M36 117q8 5 11 0 12-13 23 2m28-2q6 1 10-3 16-12 28 5" fill="none" stroke="#3a2b40" stroke-width="3" stroke-linecap="round"/>
    <g fill="#fffdf3"><circle cx="54" cy="121" r="4"/><circle cx="117" cy="121" r="4"/><circle cx="62" cy="133" r="1.6"/><circle cx="127" cy="133" r="1.6"/></g>
    <ellipse cx="43" cy="145" rx="12" ry="4.6" fill="#dc7a8c" opacity=".48"/><ellipse cx="130" cy="145" rx="12" ry="4.6" fill="#dc7a8c" opacity=".48"/>
    <path d="M89 138l3 2m-9 12q7 5 14-2" fill="none" stroke="#9d626d" stroke-linecap="round" stroke-width="2"/>
    '''
    face = '' if back else '''<ellipse cx="88" cy="115" rx="64" ry="59" fill="url(#skin)" stroke="#8c606c" stroke-width="2.4"/>
    <ellipse cx="27" cy="134" rx="8" ry="10" fill="#efb9a2"/><ellipse cx="149" cy="132" rx="8" ry="10" fill="#efb9a2"/>'''
    fringe = ('M28 131Q8 94 32 57 59 20 106 28q64 6 66 65 5 38-22 73-20 14-49 18-40 12-70-9Z' if back else
              'M29 126Q12 94 34 60q21-35 61-35 49-2 68 36 14 27-13 71l-7-29q-5-7-14-14l-7 20q-4-20-21-38-10 34-38 41l7-21q-16 16-41 35Z')
    return f'''<g transform="translate({x} {y}) scale({scale})" stroke-linejoin="round">
      <ellipse cx="95" cy="314" rx="92" ry="16" fill="#101927" opacity=".75" filter="url(#fog)"/>
      <path d="M57 262q28 6 32 22l-4 18q1 13-13 15H49q-11 0-10-8 2-10 14-14Z M101 271q16-11 30-8l8 31q17 4 17 14 0 9-16 9h-21q-12-2-12-15Z" fill="#483a58" stroke="#252c42" stroke-width="3"/>
      <path d="M59 299l17-1m48-1 16 1" stroke="#d6acaa" stroke-width="3" stroke-linecap="round"/>
      <path d="M44 161q-25-17-26-50-2-39 25-65 43-46 97-15 35 23 40 68 8 39-12 69l-12 29-124-8q18-11 12-28Z" fill="url(#hair)" stroke="#44394e" stroke-width="3"/>
      <path d="M57 164q30 5 69-2 23 13 28 36l9 38 20 46q-27 23-65 13-32 12-59 0-20 3-40-14l17-44q2-40 21-73Z" fill="url(#cape)" stroke="#41666c" stroke-width="3"/>
      <path d="M44 190Q22 211 9 230l12 15q19-9 36-42M134 181q22 3 54 21l-4 16q-23-1-51-15" fill="url(#cape)" stroke="#456971" stroke-width="2.6"/>
      <path d="M184 202q7-8 20-5 7 5 4 11-6 6-22 8Z" fill="url(#skin)" stroke="#9c6e78" stroke-width="2"/>
      <path d="M81 200q-19 58-24 84m67-82q7 49 22 80m-44-50-6 59" fill="none" stroke="#cce5bb" stroke-width="2.3" opacity=".47"/>
      <path d="M22 274q29 16 51 12 42 14 103-12" fill="none" stroke="#dbdca5" stroke-width="2.8" opacity=".83"/>
      {face}{eyes}
      <path d="{fringe}" fill="url(#hair)" stroke="#554158" stroke-width="2.5"/>
      <path d="M30 94Q50 46 103 44q46 2 57 34M39 91q21-41 65-40q28 0 44 16" stroke="#c4a1ad" stroke-width="2.5" fill="none" opacity=".58" stroke-linecap="round"/>
      <path d="M24 123q10 28 4 45 20-9 26-31m86-17q-4 34 12 48 16-15 20-48" fill="url(#hair)" stroke="#57445b" stroke-width="2"/>
      <path d="M48 161q32 19 85-2l9 16q-39 28-90 6Z" fill="#c98d87" stroke="#805e72" stroke-width="2.7"/>
      <path d="M118 175q7 25 20 45l-15 5-18-45" fill="#db9b88" stroke="#926c78" stroke-width="2"/>
      <path d="M137 78l6 6-2 8-8-3-4-7 8-4Z" fill="#fff1b2" stroke="#b99579" stroke-width="1.7"/><circle cx="151" cy="96" r="3.7" fill="#f1dab0"/>
      <circle cx="94" cy="184" r="5" fill="#c8f0db" stroke="#57776d" stroke-width="1.6"/>
    </g>'''


def creature(x, y, scale):
    return f'''<g transform="translate({x} {y}) scale({scale})" stroke-linejoin="round">
    <ellipse cx="52" cy="80" rx="75" ry="42" fill="url(#gold)"/>
    <path d="M54 81q48-60 81-37-3 44-39 49l-39-3Z" fill="url(#fox)" stroke="#a87f83" stroke-width="2.3"/>
    <path d="M115 67q14-10 20-23-19-9-34 4 5 12 14 19Z" fill="#fff4d3"/>
    <path d="M23 69Q-1 61 5 34L0 10Q22 3 38 24l20-2Q72 0 96 5l-9 34q13 21-3 36-9 9-25 11l-1 11q-21 10-42 0l7-28Z" fill="url(#fox)" stroke="#896c76" stroke-width="2.5"/>
    <path d="m9 15 5 23 17-10Zm56 14 15 11 8-28Z" fill="#d48b89"/>
    <path d="M12 49q10-10 31 13 7 5 14 0 18-19 30-9-2 26-36 29-33 0-39-33Z" fill="#fff1cd"/>
    <g fill="#4e4357"><ellipse cx="29" cy="52" rx="5" ry="7"/><ellipse cx="67" cy="51" rx="5" ry="7"/><path d="M44 59q8-3 12 0l-5 6Z"/></g><g fill="#fff9df"><circle cx="27" cy="49" r="2.2"/><circle cx="65" cy="48" r="2.2"/></g>
    <path d="M52 65q-5 8-12 3m12-3q7 6 12 1" fill="none" stroke="#7b5f72" stroke-width="1.5" stroke-linecap="round"/>
    <path d="M35 22 48 8l11 14-11 12Z" fill="#ffeec0"/><ellipse cx="48" cy="19" rx="35" ry="32" fill="url(#gold)" opacity=".65"/>
    </g>'''


def flower(x, y, scale):
    petals = ''.join(f'<path transform="rotate({angle})" d="M0 3Q-32-18-18-44 2-53 16-28 24-10 0 3Z" fill="url(#petal)" stroke="#aeefff" stroke-width="1.1"/>' for angle in (0, 72, 144, 216, 288))
    return f'''<g transform="translate({x} {y}) scale({scale})">
    <path d="M-14 144Q-42 102-1 49 9 24 0-1" fill="none" stroke="#79c3aa" stroke-width="5" stroke-linecap="round"/>
    <path d="M-17 127Q-58 112-57 80-20 85-17 127Zm-4-48Q4 38 32 50q-5 25-53 29Z" fill="#62aa91" stroke="#abd5ac" stroke-width="2"/>
    {light(0,0,122,opacity=.9)}{petals}<circle r="14" fill="#dbfbff"/><circle r="6" fill="#fffde0"/>
    {light(0,0,64,opacity=.6)}
    </g>'''


def woods(scene):
    rng = random.Random(168 + scene)
    palette = (("#4b7e91", "#214653"), ("#686180", "#303e56"), ("#69988d", "#2f5759"))
    mid, deep = palette[scene]
    chunks = ['<rect width="540" height="960" fill="url(#bg)"/>', light(281, 362, 240, "wash", .85, 345)]
    for layer, color in enumerate(("#82a9ad", "#406771", "#294455", "#182d40")):
        for _ in range(23 - layer * 4):
            x, drift = rng.randrange(-45, 585), rng.randrange(-60, 42)
            bottom = 555 + layer * 107 + rng.randrange(-65, 45)
            width = rng.randrange(4, 16) + 9 * layer
            chunks.append(f'<path d="M{x} -54q{drift} 191 {drift//2} 395t{-drift//2} {bottom-341}q-{width} -13 -{width*2} 1Q{x-width} 322 {x-width*2} -54Z" fill="{color}" opacity="{.27 + layer*.19}"/>')
            for branch in range(2):
                y = rng.randrange(30, 460)
                root = x - width//3
                tx = root + rng.choice((-1,1))*rng.randrange(30,145)
                chunks.append(f'<path d="M{root} {y+83}Q{(tx+root)//2} {y+25} {tx} {y}q{(root-tx)//2} 7 {root-tx} 67Z" fill="{color}" opacity=".65"/>')
    chunks.extend(['<path d="M0 641Q107 544 242 598T540 600V960H0Z" fill="#253d47"/>', '<path d="M0 784Q170 644 248 661t97 0q139-45 195 46V960H0Z" fill="#203640"/>',
                   '<path d="M282 559q-57 77-9 100 85 50 43 95-39 39-97 54-80 27-100 152H453q20-60-9-89-52-41-37-105 18-82-122-127-25-15-3-80Z" fill="url(#path)"/>',
                   '<path d="M0 0q65 55 34 177-15 58 12 146-30 103 3 221l-31 159H0Zm540 0q-135 18-141 107l32-16 23 45 33-10 4 70 49 51Z" fill="#112235" opacity=".8"/>'])
    for _ in range(480):
        x, y = rng.randrange(550), rng.randrange(90, 963)
        opacity = rng.uniform(.1, .41) * (1 if y > 575 else .53)
        size = rng.uniform(1.1, 9) * (1 if y > 575 else .84)
        color = rng.choice(("#87ae9e", "#526c79", "#b1bca5", "#638b8f", "#24394f"))
        chunks.append(f'<path d="M{x} {y}q{size:.1f} -{size:.1f} {size*2.1:.1f} -{size*.78:.1f} -{size*.8:.1f} {size*1.11:.1f} -{size*2.1:.1f} {size*.78:.1f}Z" fill="{color}" opacity="{opacity:.2f}"/>')
    return mid, deep, ''.join(chunks)


def roots():
    return '''<path d="M273-26h267v813q-38-32-62-44-36-35-84-30-78-45-128 4 12-49 55-79-20-71 5-146 18-66-29-189L228 171 288 211 229 89l92 97q12-96-48-212Z" fill="url(#bark)" stroke="#252c43" stroke-width="4"/>
    <path d="M398-42Q379 87 399 243t-23 357q-47 10-74 65m175-659q-34 228-19 365 12 119-25 222 48 13 72 79" fill="none" stroke="#9b938c" stroke-width="5" opacity=".24"/>
    <path d="M541 643q-102-77-147-62-57 10-54 109 107-18 201 68Z" fill="#1e253b"/>
    <path d="M540 759q-74-55-147-64-57-37-161 28-27 17-88 9 68 31 128 13 86-27 140 7 62 42 128 52Zm-22 26q-67-12-91 9-21 26-87 45 84 8 142-10 30-6 58-1Z" fill="url(#bark)" stroke="#293345" stroke-width="4"/>
    <path d="M172 741q62 4 113-31t110-18q52 4 141 66m-196 84q72-2 136-32" fill="none" stroke="#7d9e94" opacity=".45" stroke-width="4" stroke-linecap="round"/>'''


def motes(scene):
    rng = random.Random(412 + scene)
    chunks = []
    for n in range((52, 56, 121)[scene]):
        x, y = rng.randrange(12, 532), rng.randrange(145, 911)
        color = "gold" if (scene == 2 and n % 3 != 0 or scene == 1 and x > 285) else "cyan"
        s = rng.uniform(.64, 2.5)
        if n % 3 == 0:
            chunks.append(light(x,y,round(8 + s*8),color,.78))
        ink = "#ffefba" if color == "gold" else "#b9f8ec"
        chunks.append(f'<circle cx="{x}" cy="{y}" r="{s:.1f}" fill="{ink}" opacity="{rng.uniform(.34,.98):.2f}"/>')
        if n % 11 == 0:
            chunks.append(f'<path d="M{x-6} {y}q6 0 6-8 0 8 6 8-6 0-6 8 0-8-6-8Z" fill="{ink}" opacity=".8"/>')
    return ''.join(chunks)


def frame(scene, study=False):
    mid, deep, background = woods(scene)
    if scene == 0:
        action = (light(374, 579, 209, "cyan", .66) + girl(56,455,1.14) + flower(390,611,.99))
    elif scene == 1:
        action = (roots() + light(394, 662, 134, "gold", .34 if study else .51) +
                  (creature(351,650,.66) + girl(51,507,.98) + flower(269,705,.59) if study
                   else creature(346,621,.79) + girl(37,534,.88) + flower(230,695,.55)))
    else:
        action = (light(311,461,280,"gold",.58,391) + light(179,421,232,"wash",.74,300) + girl(168,649,.68,back=True) +
                  creature(318,792,.6) + flower(343,722,.42))
    accents = ''.join(f'<path d="M{x} 960q0-40 {dx} -{height} {(-dx*.7):.1f} {height*.26:.1f} {-dx} {height}Z" fill="{color}" opacity=".8"/>'
                      for x, dx, height, color in ((-3,62,146,'#204950'),(63,-39,108,'#386a65'),(74,39,86,'#385d64'),(490,-72,109,'#31616a'),(532,-76,206,'#173645'),(503,31,139,'#385965')))
    return svg(mid, deep, background+action+motes(scene)+accents)


def svg(mid, deep, content):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="540" height="960" viewBox="0 0 540 960"><defs>{DEFS.replace("MID",mid).replace("DEEP",deep)}</defs>' + content +
            '<rect width="540" height="960" fill="url(#edge)"/><rect width="540" height="960" filter="url(#paper)" opacity=".18" style="mix-blend-mode:soft-light"/></svg>')


def reference(fox=False):
    background = ('<rect width="540" height="960" fill="url(#bg)"/><path d="M50 133h440v702H50Z" fill="none" stroke="#bdd7d3" opacity=".35"/>'
                  '<circle cx="270" cy="475" r="181" fill="none" stroke="#c6edda" opacity=".36"/><circle cx="270" cy="475" r="196" fill="none" stroke="#c6edda" opacity=".22"/>'
                  '<path d="M50 165h30v-32m380 0v32h30M50 802h30v32m380 0v-32h30" fill="none" stroke="#bde0d9" opacity=".62" stroke-width="2"/>')
    subject = creature(104, 366, 2.5) if fox else girl(100,242,1.82)
    return svg('#675d7e' if fox else '#567c90', '#3b4867', background + light(280,478,257,"gold" if fox else "wash",.54 if fox else 1) + subject)


if __name__ == '__main__':
    directory = Path(sys.argv[1])
    directory.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(('flower', 'old-tree', 'forest-lights')):
        (directory / f'{name}.svg').write_text(frame(index), encoding='utf-8')
    (directory / 'old-tree-study.svg').write_text(frame(1, study=True), encoding='utf-8')
    (directory / 'traveler-reference.svg').write_text(reference(), encoding='utf-8')
    (directory / 'creature-reference.svg').write_text(reference(fox=True), encoding='utf-8')
