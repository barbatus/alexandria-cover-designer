"""Prompt library system for reusable, title-agnostic generation prompts (Prompt 2A)."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

try:
    from src import config
    from src import safe_json
    from src.logger import get_logger
except ModuleNotFoundError:  # pragma: no cover
    import config  # type: ignore
    import safe_json  # type: ignore
    from logger import get_logger  # type: ignore

logger = get_logger(__name__)

SUPPORTED_REUSABLE_PLACEHOLDERS: tuple[str, ...] = (
    "{title}",
    "{author}",
    "{TITLE}",
    "{AUTHOR}",
    "{SUBTITLE}",
    "{SCENE}",
    "{MOOD}",
    "{ERA}",
)

ALEXANDRIA_SYSTEM_NEGATIVE_PROMPT = (
    "No text, no letters, no words, no numbers, no titles, no author names, no typography, no captions, "
    "no labels, no watermarks, no signatures, no inscriptions of any kind. No modern elements, no photography, "
    "no 3D rendering, no digital art aesthetic, no gradients on background, no neon colours, no sans-serif fonts, "
    "no minimalist design, no stock photo look, no cartoonish style, no anime influence, no spelling mistakes, "
    "no blurry illustration, no off-centre composition, no white or light backgrounds. "
    "No dividers."
)

ALEXANDRIA_BASE_NEGATIVE_PROMPT = (
    "text, letters, words, numbers, titles, typography, watermarks, signatures, 3D rendering, CGI, "
    "photography, digital art sheen, smooth digital gradients, plastic surfaces, AI-generated look, "
    "vector art, anime, cartoon, blurry, stock photo"
)

ALEXANDRIA_PAINTERLY_TEXTURE_CLAUSE = (
    "Every stroke must show the physical texture of hand-applied paint."
)

ALEXANDRIA_WILDCARD_TEXTURE_CLAUSE = (
    "Rendered with the physical texture of traditional handmade artwork."
)

ALEXANDRIA_BASE_PROMPT_TEMPLATES: dict[str, str] = {
    "alexandria-base-classical-devotion": (
        "Book cover illustration — no text, no lettering. Scene: {SCENE}. STYLE: Rich oil painting, "
        "hyper-detailed botanical precision. Deep midnight navy and burnished gold. Thick impasto on "
        "gilded elements, fine detail on flora. Sacred, warm candlelight glow. Mood: {MOOD}. Era: {ERA}. "
        "Visible brushwork on canvas throughout."
    ),
    "alexandria-base-philosophical-gravitas": (
        "Book cover illustration — no text, no lettering. Scene: {SCENE}. STYLE: Dramatic chiaroscuro. "
        "Strong light carves figures from shadow. Raw umber and burnt sienna dominate, gold ochre warms "
        "the light, charcoal grey deepens shadow. Heavy Rembrandt-era texture. Mood: {MOOD}. Era: {ERA}. "
        "Thick impasto paint texture on every surface."
    ),
    "alexandria-base-gothic-atmosphere": (
        "Book cover illustration — no text, no lettering. Scene: {SCENE}. STYLE: Dark atmospheric "
        "painting, expressionist energy. Loose aggressive brushwork with palette knife marks. Moonlit "
        "indigo and deep crimson with silvered edge highlights. Gothic tension, foreboding atmosphere. "
        "Mood: {MOOD}. Era: {ERA}. Ink-wash texture with visible paper grain."
    ),
    "alexandria-base-romantic-realism": (
        "Book cover illustration — no text, no lettering. Scene: {SCENE}. STYLE: Warm romantic landscape, "
        "19th-century Romanticism. Soft luminous brushwork, watercolor washes over oil. Golden-hour amber "
        "and warm sienna, soft sky blue, deep forest green. Sweeping atmospheric perspective. Mood: "
        "{MOOD}. Era: {ERA}. Oil paint texture with visible canvas weave."
    ),
    "alexandria-base-esoteric-mysticism": (
        "Book cover illustration — no text, no lettering. Scene: {SCENE}. STYLE: Visionary painting with "
        "luminous depth. Translucent glazes create inner glow. Cosmic indigo and celestial gold, deep "
        "amethyst, ethereal silver-white. Mystical symbols emerge from luminous mist. Mood: {MOOD}. "
        "Era: {ERA}. Hand-painted texture with pigment granulation."
    ),
}


def _base_prompt_template(prompt_id: str) -> str:
    return ALEXANDRIA_BASE_PROMPT_TEMPLATES[prompt_id]


def _wildcard_texture_clause(prompt_id: str) -> str:
    if "painterly" in str(prompt_id or ""):
        return ALEXANDRIA_PAINTERLY_TEXTURE_CLAUSE
    return ALEXANDRIA_WILDCARD_TEXTURE_CLAUSE


def _scene_first_prompt(
    style_label: str,
    style_description: str,
    *,
    style_section: str = "",
    full_canvas: bool = False,
    texture_clause: str = "",
) -> str:
    del style_section, full_canvas
    rendered_section = f"{style_label} — {style_description}".strip(" —")
    prompt = (
        "Book cover illustration — no text, no lettering. "
        f"Scene: {{SCENE}}. STYLE: {rendered_section}. Mood: {{MOOD}}. Era: {{ERA}}."
    )
    if texture_clause.strip():
        prompt = f"{prompt} {texture_clause.strip()}"
    return prompt


ALEXANDRIA_PROMPT_CATALOG: tuple[dict[str, object], ...] = (
    {
        "id": "alexandria-base-classical-devotion",
        "name": "BASE 1 — Classical Devotion",
        "style_label": "Art Nouveau Pre-Raphaelite illustration",
        "style_description": (
            "deep midnight navy blue background tones, warm burnished gold and antique brass highlights, rich "
            "cobalt and cerulean blue mid-tones, earth ochre and burnt sienna for landscapes, fine botanical "
            "detail in every flower and leaf, flowing lines and romantic composition, figures in hyper-detailed "
            "period clothing with flowing hair and emotional poses, lush pastoral settings with castles and rivers "
            "and wildflower gardens, painterly brushwork with visible gilded texture like an illuminated manuscript"
        ),
        "prompt_template": _base_prompt_template("alexandria-base-classical-devotion"),
        "full_canvas": True,
        "negative_prompt": ALEXANDRIA_BASE_NEGATIVE_PROMPT,
        "notes": "Alexandria base prompt. Best for: Religious, Apocryphal, Biblical.",
        "tags": ["alexandria", "base", "classical-devotion", "religious", "apocryphal", "biblical"],
        "category": "builtin",
    },
    {
        "id": "alexandria-base-philosophical-gravitas",
        "name": "BASE 2 — Philosophical Gravitas",
        "style_label": "contemplative chiaroscuro illustration",
        "style_description": (
            "deep shadows, selective warm highlights, muted burnt umber and ochre palette, single focal light "
            "source, grave reflective atmosphere"
        ),
        "prompt_template": _base_prompt_template("alexandria-base-philosophical-gravitas"),
        "full_canvas": True,
        "negative_prompt": ALEXANDRIA_BASE_NEGATIVE_PROMPT,
        "notes": "Alexandria base prompt. Best for: Philosophy, Self-Help, Strategy.",
        "tags": ["alexandria", "base", "philosophical-gravitas", "philosophy", "self-help", "strategy"],
        "category": "builtin",
    },
    {
        "id": "alexandria-base-gothic-atmosphere",
        "name": "BASE 3 — Gothic Atmosphere",
        "style_label": "dark atmospheric Gothic illustration",
        "style_description": (
            "moonlit shadows, drifting mist, deep indigo and crimson tones, expressionist contrast, dramatic "
            "silhouettes against turbulent skies"
        ),
        "prompt_template": _base_prompt_template("alexandria-base-gothic-atmosphere"),
        "full_canvas": True,
        "negative_prompt": ALEXANDRIA_BASE_NEGATIVE_PROMPT,
        "notes": "Alexandria base prompt. Best for: Horror, Gothic, Supernatural.",
        "tags": ["alexandria", "base", "gothic-atmosphere", "horror", "gothic", "supernatural"],
        "category": "builtin",
    },
    {
        "id": "alexandria-base-romantic-realism",
        "name": "BASE 4 — Romantic Realism",
        "style_label": "romantic Pre-Raphaelite realism with Art Nouveau influence",
        "style_description": (
            "deep navy and midnight blue shadows, warm gold and amber light sources, rich crimson and ivory in "
            "clothing, detailed historical costumes with embroidery and flowing fabric, botanical precision in "
            "every plant and flower, dramatic skies with swirling clouds in blues and golds, lush gardens and "
            "medieval architecture in the background, figures with flowing auburn or golden hair in emotional "
            "intimate compositions, painterly brushwork like a gilded 19th-century illustration"
        ),
        "prompt_template": _base_prompt_template("alexandria-base-romantic-realism"),
        "full_canvas": True,
        "negative_prompt": ALEXANDRIA_BASE_NEGATIVE_PROMPT,
        "notes": "Alexandria base prompt. Best for: Classical Literature, Novels, Drama.",
        "tags": ["alexandria", "base", "romantic-realism", "literature", "novels", "drama"],
        "category": "builtin",
    },
    {
        "id": "alexandria-base-esoteric-mysticism",
        "name": "BASE 5 — Esoteric Mysticism",
        "style_label": "esoteric mystical illustration",
        "style_description": (
            "celestial motifs, sacred geometry accents, deep midnight blue and gold palette, luminous ethereal "
            "lighting, symbolic depth"
        ),
        "prompt_template": _base_prompt_template("alexandria-base-esoteric-mysticism"),
        "full_canvas": True,
        "negative_prompt": ALEXANDRIA_BASE_NEGATIVE_PROMPT,
        "notes": "Alexandria base prompt. Best for: Occult, Mystical, Forbidden Texts.",
        "tags": ["alexandria", "base", "esoteric-mysticism", "occult", "mystical", "esoteric"],
        "category": "builtin",
    },
    {
        "id": "alexandria-wildcard-edo-meets-alexandria",
        "name": "WILDCARD 1 — Dramatic Graphic Novel",
        "style_label": "dramatic graphic novel engraving",
        "style_description": (
            "bold parallel crosshatching, heavy black outlines, expressive faces in close-up, deep black with "
            "warm amber and burnt orange highlights, swirling dramatic sky"
        ),
        "notes": "Alexandria wildcard prompt. Dramatic amber-black engraving with graphic novel poster energy.",
        "tags": ["alexandria", "wildcard", "dramatic-graphic-novel", "graphic-novel", "crosshatch", "dramatic"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-pre-raphaelite-garden",
        "name": "WILDCARD 2 — Vintage Travel Poster",
        "style_label": "bold 1930s vintage travel poster",
        "style_description": (
            "flat unblended colour blocks with clean outlines, layered depth planes, burgundy navy cream and "
            "forest green palette, geometric confidence"
        ),
        "notes": "Alexandria wildcard prompt. Flat-colour travel-poster composition with bold geometric depth.",
        "tags": ["alexandria", "wildcard", "vintage-travel-poster", "travel-poster", "graphic", "flat-color"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-illuminated-manuscript",
        "name": "WILDCARD 3 — Illuminated Manuscript",
        "style_label": "medieval illuminated manuscript",
        "style_description": (
            "gold leaf accents, ultramarine blue and vermilion, intricate marginalia patterns, flat perspective "
            "with symbolic scale, rich decorative detail"
        ),
        "notes": "Alexandria wildcard prompt. Medieval manuscript energy for ancient or sacred material.",
        "tags": ["alexandria", "wildcard", "illuminated-manuscript", "medieval", "celtic"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-celestial-cartography",
        "name": "WILDCARD 4 — Celestial Cartography",
        "style_label": "scientific cartographic illustration",
        "style_description": (
            "compass roses, parchment tones, precise linework, sepia and aged-gold palette, navigational chart "
            "aesthetics, hand-drawn map detail"
        ),
        "notes": "Alexandria wildcard prompt. Cosmic engraving language for knowledge-rich or metaphysical titles.",
        "tags": ["alexandria", "wildcard", "celestial-cartography", "celestial", "astronomy"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-temple-of-knowledge",
        "name": "WILDCARD 5 — Temple of Knowledge",
        "style_label": "monumental architectural illustration",
        "style_description": (
            "classical columns, dramatic perspective, warm lamplight on stone, scrolls and books as decorative "
            "elements, sepia and amber palette with selective gold highlights"
        ),
        "notes": "Alexandria wildcard prompt. Direct homage to Alexandria's Egyptian origin and temple symbolism.",
        "tags": ["alexandria", "wildcard", "temple-of-knowledge", "egyptian", "mystical"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-venetian-renaissance",
        "name": "Venetian Renaissance",
        "style_label": "Venetian Renaissance oil painting",
        "style_description": (
            "Titian-warm glazes, luminous skin tones, rich velvet and brocade fabrics, atmospheric sfumato "
            "backgrounds, deep jewel-tone crimson sapphire and gold palette"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Venetian Renaissance painting — warm, glowing colour applied in rich glazes "
            "over warm underpaint. Soft transitions between light and shadow (sfumato). Lush landscapes recede "
            "into atmospheric blue distance. Figures have warm, luminous skin painted with multiple translucent "
            "layers. Palette: warm Venetian red, deep ultramarine blue, rich gold, soft green, rosy flesh tones. "
            "The paint surface glows with inner warmth. Like Titian or Giorgione."
        ),
        "notes": "Alexandria wildcard prompt. Venetian Renaissance richness with glowing jewel-tone depth.",
        "tags": ["alexandria", "wildcard", "venetian-renaissance", "classical", "fine-art"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-dutch-golden-age",
        "name": "Dutch Golden Age",
        "style_label": "Dutch Golden Age painting",
        "style_description": (
            "Rembrandt-like chiaroscuro, intimate domestic lighting, meticulous fabric texture, warm amber and "
            "deep brown palette, candlelit atmosphere with selective highlights"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Dutch Golden Age painting — intimate domestic scenes lit by soft window light "
            "from the left side. Extraordinary attention to material textures: reflective metals, translucent "
            "glass, soft bread, worn leather, starched linen. Rich dark backgrounds with warm pools of light. "
            "Palette: deep brown, warm gold, cream white, touches of vermillion red and ultramarine blue. Every "
            "surface texture is rendered with loving precision. Like Vermeer or Rembrandt."
        ),
        "notes": "Alexandria wildcard prompt. Dutch interior drama with intimate candlelit precision.",
        "tags": ["alexandria", "wildcard", "dutch-golden-age", "classical", "fine-art"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-impressionist-plein-air",
        "name": "Impressionist Plein Air",
        "style_label": "French Impressionist plein air",
        "style_description": (
            "visible brushstrokes, dappled natural sunlight, soft focus atmospheric depth, luminous pastel and "
            "sky-blue palette, Monet-like light on water and foliage"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: French Impressionist plein air painting — loose visible brushstrokes "
            "throughout, dappled natural sunlight filtering through foliage creates dancing spots of warm yellow "
            "and cool blue shadow. Paint applied in thick impasto dabs of pure colour placed side by side "
            "(NOT blended). Soft atmospheric haze in the distance. Palette: luminous sky blue, lavender, soft "
            "pink, leaf green, sunshine yellow. The texture of oil paint on canvas is visible in every stroke. "
            "Like a Monet or Renoir painting."
        ),
        "notes": "Alexandria wildcard prompt. Sunlit Impressionist atmosphere with airy painterly motion.",
        "tags": ["alexandria", "wildcard", "impressionist-plein-air", "classical", "fine-art"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-academic-neoclassical",
        "name": "Academic Neoclassical",
        "style_label": "Academic Neoclassical painting",
        "style_description": (
            "idealized proportions, marble-smooth surfaces, heroic poses, cool grey-blue and warm sandstone "
            "palette, classical architectural framing, David-like precision and grandeur"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Academic Neoclassical painting — precise, refined technique with smooth "
            "blended brushwork and idealized forms. Figures have classical proportions with noble poses. "
            "Architecture features columns, arches, and marble. Palette: cool marble white, warm ochre, sky "
            "blue, laurel green, with skin tones in warm peach and rose. Balanced, symmetrical compositions with "
            "clear focal hierarchy. Like Jacques-Louis David or Bouguereau."
        ),
        "notes": "Alexandria wildcard prompt. Neoclassical grandeur with disciplined heroic staging.",
        "tags": ["alexandria", "wildcard", "academic-neoclassical", "classical", "fine-art"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-baroque-dramatic",
        "name": "Baroque Dramatic",
        "style_label": "Baroque dramatic painting",
        "style_description": (
            "Caravaggio-intense spotlighting, deep blacks with explosive warm highlights, theatrical gesture and "
            "expression, swirling drapery, rich crimson and gold against darkness"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Baroque dramatic painting — theatrical lighting with extreme contrast between "
            "deep shadow and brilliant warm light. Rich, heavy oil paint texture with visible brushwork. Fabric "
            "rendered with luxurious weight and sheen — velvet, silk, brocade. Dramatic diagonal compositions "
            "with figures in dynamic poses. Palette: deep Venetian red, burnt gold, warm flesh tones against "
            "near-black shadow. Warm candlelight or divine light breaks through darkness. Like Caravaggio or "
            "Rubens."
        ),
        "notes": "Alexandria wildcard prompt. Baroque spotlighting with theatrical emotional force.",
        "tags": ["alexandria", "wildcard", "baroque-dramatic", "classical", "fine-art"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-art-nouveau-poster",
        "name": "Art Nouveau Poster",
        "style_label": "Art Nouveau illustration",
        "style_description": (
            "sinuous organic linework, flowing hair and fabric, jewel-tone flat colours with gold outlines, "
            "Mucha-inspired decorative elegance, nature-integrated composition"
        ),
        "notes": "Alexandria wildcard prompt. Art Nouveau elegance with flowing decorative rhythm.",
        "tags": ["alexandria", "wildcard", "art-nouveau-poster", "illustration", "graphic"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-vintage-pulp-cover",
        "name": "Vintage Pulp Cover",
        "style_label": "1940s vintage pulp illustration",
        "style_description": (
            "saturated primary colours, high-contrast dramatic lighting, bold expressive faces, painterly gouache "
            "texture, action-forward composition with dynamic diagonals"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Vintage pulp magazine cover painting — bold, saturated colours with dramatic "
            "action-oriented composition. Thick gouache paint texture with visible brushwork. Strong warm "
            "spotlight on the main figure against dark or dramatic backgrounds. Palette: bold primary colours — "
            "vivid red, deep blue, bright yellow — with warm skin tones and dark shadows. Dynamic poses, dramatic "
            "expressions. The handpainted quality of mid-20th century illustration."
        ),
        "notes": "Alexandria wildcard prompt. Pulpy action illustration with bold mid-century energy.",
        "tags": ["alexandria", "wildcard", "vintage-pulp-cover", "illustration", "graphic"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-woodcut-relief",
        "name": "Woodcut Relief Print",
        "style_label": "hand-carved woodcut relief print",
        "style_description": (
            "bold black lines on warm cream, hatched shadow textures, simplified dramatic forms, limited "
            "two-tone palette, Dürer-inspired precision with folk art warmth"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Woodcut relief print illustration — bold black outlines with carved texture "
            "visible in every line. Cross-hatching and parallel line shading create tonal depth. Limited colour "
            "palette applied in flat areas between carved lines. Palette: deep black ink, warm parchment, with "
            "optional touches of muted red, blue, or green. The texture of carved wood grain visible "
            "throughout. Bold, graphic, with the handmade quality of a physical print."
        ),
        "notes": "Alexandria wildcard prompt. Woodcut austerity with carved graphic punch.",
        "tags": ["alexandria", "wildcard", "woodcut-relief", "illustration", "graphic"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-art-deco-glamour",
        "name": "Art Deco Glamour",
        "style_label": "Art Deco glamour illustration",
        "style_description": (
            "geometric symmetry, sleek metallic gold and silver accents, jade green and midnight black palette, "
            "elongated elegant figures, Chrysler Building-era luxury and angular precision"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Art Deco illustration — sleek geometric elegance with stylized figures and "
            "architectural forms. Clean, precise lines with areas of rich flat colour. Metallic gold and silver "
            "accents. Palette: black, gold, silver, deep teal, cream white, coral. Figures are elongated and "
            "elegant. Geometric sunburst and zigzag patterns in backgrounds. Painted with precision and glamour. "
            "Like Erte or Tamara de Lempicka."
        ),
        "notes": "Alexandria wildcard prompt. Art Deco luxury with angular metropolitan polish.",
        "tags": ["alexandria", "wildcard", "art-deco-glamour", "illustration", "graphic"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-soviet-constructivist",
        "name": "Soviet Constructivist",
        "style_label": "Soviet Constructivist poster",
        "style_description": (
            "bold angular composition, red black cream and steel grey palette, photomontage-inspired layering, "
            "diagonal dynamic energy, heroic monumental scale"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Soviet Constructivist poster painting — bold geometric shapes, strong diagonal "
            "compositions, dynamic angular figures in heroic poses. Flat colour areas with sharp edges and "
            "limited palette. Palette: revolutionary red, deep black, warm cream/gold, industrial grey. Bold "
            "graphic shapes layered with photomontage-inspired depth. Heavy, powerful brushwork with visible "
            "texture. Like El Lissitzky or Alexander Rodchenko."
        ),
        "notes": "Alexandria wildcard prompt. Constructivist urgency with bold political poster force.",
        "tags": ["alexandria", "wildcard", "soviet-constructivist", "illustration", "graphic"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-ukiyo-e-woodblock",
        "name": "Ukiyo-e Woodblock",
        "style_label": "Japanese ukiyo-e woodblock print",
        "style_description": (
            "flat colour planes with precise black outlines, asymmetric composition, indigo and vermilion palette, "
            "stylized wave and cloud motifs, Hokusai-inspired naturalistic detail"
        ),
        "notes": "Alexandria wildcard prompt. Ukiyo-e clarity with strong asymmetric composition.",
        "tags": ["alexandria", "wildcard", "ukiyo-e-woodblock", "eastern", "cross-cultural"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-persian-miniature",
        "name": "Persian Miniature",
        "style_label": "Persian miniature painting",
        "style_description": (
            "bird's-eye multi-level perspective, jewel-bright lapis lazuli and emerald palette, intricate floral "
            "details, gold leaf accents, delicate figure rendering with expressive faces"
        ),
        "notes": "Alexandria wildcard prompt. Persian miniature luminosity with jewel-bright layered perspective.",
        "tags": ["alexandria", "wildcard", "persian-miniature", "eastern", "cross-cultural"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-chinese-ink-wash",
        "name": "Chinese Ink Wash",
        "style_label": "Chinese ink wash painting",
        "style_description": (
            "misty mountain atmosphere, graded ink tones from deep black to pale grey, negative space as a "
            "compositional element, bamboo-brush spontaneity, Song dynasty landscape grandeur"
        ),
        "notes": "Alexandria wildcard prompt. Ink-wash restraint with spacious atmospheric depth.",
        "tags": ["alexandria", "wildcard", "chinese-ink-wash", "eastern", "cross-cultural"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-ottoman-illumination",
        "name": "Ottoman Illumination",
        "style_label": "Ottoman illuminated manuscript",
        "style_description": (
            "turquoise and coral palette with gold filigree, tulip and carnation motifs, flat decorative "
            "perspective, intricate geometric borders, courtly mineral-pigment elegance"
        ),
        "notes": "Alexandria wildcard prompt. Ottoman courtly illumination with vibrant mineral ornament.",
        "tags": ["alexandria", "wildcard", "ottoman-illumination", "eastern", "cross-cultural"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-film-noir-shadows",
        "name": "Film Noir Shadows",
        "style_label": "film noir cinematic",
        "style_description": (
            "high-contrast black and white with selective warm amber highlights, venetian blind shadow patterns, "
            "rain-slicked surfaces, cigarette-smoke atmosphere, dramatic low-angle perspective"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Film noir painting — extreme high-contrast with deep shadows occupying most of "
            "the canvas. Sharp-edged shadows and dramatic angular light from venetian blinds, street lamps, or "
            "doorways. Figures are partially obscured by shadow, creating mystery and tension. Palette: "
            "near-black shadows, cool blue-grey mid-tones, sharp white highlights, occasional warm amber from a "
            "single light source. Painted with bold confident strokes. Like a painted movie poster from the "
            "1940s."
        ),
        "notes": "Alexandria wildcard prompt. Noir contrast with smoky urban menace.",
        "tags": ["alexandria", "wildcard", "film-noir-shadows", "atmospheric", "moody"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-pre-raphaelite-dream",
        "name": "Pre-Raphaelite Dream",
        "style_label": "Pre-Raphaelite painting",
        "style_description": (
            "jewel-bright saturated colours, hyper-detailed botanical elements, flowing auburn hair and "
            "medieval-inspired drapery, Waterhouse-like romantic atmosphere"
        ),
        "notes": "Alexandria wildcard prompt. Pre-Raphaelite romanticism with lush botanical intensity.",
        "tags": ["alexandria", "wildcard", "pre-raphaelite-dream", "atmospheric", "moody"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-twilight-symbolism",
        "name": "Twilight Symbolism",
        "style_label": "Symbolist painting",
        "style_description": (
            "dreamlike twilight atmosphere, deep purple and midnight blue palette with phosphorescent accents, "
            "enigmatic figure poses, Redon-inspired otherworldly luminescence, mythology blended with nature"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Symbolist painting — dreamlike soft-focus atmosphere where forms dissolve at "
            "their edges into mist and shadow. Twilight lighting with the sky transitioning from deep blue to "
            "pale gold at the horizon. Figures emerge from shadow as if materializing from a dream. Palette: "
            "deep twilight blue, soft violet, pale gold, muted rose, silvery grey. Smooth, luminous brushwork "
            "with a mysterious inner glow. Like Odilon Redon or Fernand Khnopff."
        ),
        "notes": "Alexandria wildcard prompt. Symbolist twilight with strange luminous mood.",
        "tags": ["alexandria", "wildcard", "twilight-symbolism", "atmospheric", "moody"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-northern-renaissance",
        "name": "Northern Renaissance",
        "style_label": "Northern Renaissance oil painting",
        "style_description": (
            "Van Eyck meticulous detail, cool silvery light through leaded glass windows, rich textile patterns, "
            "precise botanical accuracy, intimate domestic scale with symbolic objects"
        ),
        "style_section": (
            "RENDERING TECHNIQUE: Northern Renaissance painting — extraordinary microscopic detail in every "
            "surface. Every hair, every thread, every wood grain, every reflection in glass or metal is "
            "individually rendered with a fine-pointed brush. Crystal-clear focus from foreground to background. "
            "Rich jewel-tone colours with luminous depth from oil glazes. Palette: deep blue, ruby red, emerald "
            "green, warm gold, all with gem-like luminosity. Like Jan van Eyck or Albrecht Dürer."
        ),
        "notes": "Alexandria wildcard prompt. Northern Renaissance precision with intimate symbolic detail.",
        "tags": ["alexandria", "wildcard", "northern-renaissance", "atmospheric", "moody"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-william-morris-textile",
        "name": "William Morris Textile",
        "style_label": "William Morris Arts and Crafts",
        "style_description": (
            "intertwining vines and birds framing the scene, muted sage green and indigo palette, hand-printed "
            "woodblock texture, medieval-inspired naturalism, Kelmscott Press decorative richness"
        ),
        "notes": "Alexandria wildcard prompt. Arts and Crafts ornament with hand-printed texture.",
        "tags": ["alexandria", "wildcard", "william-morris-textile", "decorative", "ornamental"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-klimt-gold-leaf",
        "name": "Klimt Gold Leaf",
        "style_label": "Gustav Klimt decorative",
        "style_description": (
            "lavish gold leaf mosaic patterns integrated with realistic figures, Byzantine-inspired geometric "
            "abstraction, warm ochre and deep emerald palette, sensuous flowing forms"
        ),
        "notes": "Alexandria wildcard prompt. Klimt-like ornament with sensuous gold mosaic richness.",
        "tags": ["alexandria", "wildcard", "klimt-gold-leaf", "decorative", "ornamental"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-celtic-knotwork",
        "name": "Celtic Knotwork",
        "style_label": "Celtic illuminated manuscript",
        "style_description": (
            "interlaced knotwork framing the scene, Book of Kells-inspired zoomorphic details, deep forest green "
            "and burnished gold palette, spiralling decorative accents, insular art precision"
        ),
        "notes": "Alexandria wildcard prompt. Celtic manuscript knotwork with mythic illuminated precision.",
        "tags": ["alexandria", "wildcard", "celtic-knotwork", "decorative", "ornamental"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-botanical-plate",
        "name": "Botanical Plate",
        "style_label": "18th-century botanical illustration",
        "style_description": (
            "precise scientific observation, delicate hand-tinted watercolour washes on cream paper, naturalist "
            "field-drawing accuracy, muted sage and rose palette, Redouté-inspired elegance"
        ),
        "notes": "Alexandria wildcard prompt. Botanical illustration discipline with delicate naturalist grace.",
        "tags": ["alexandria", "wildcard", "botanical-plate", "cartographic", "scientific"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-antique-map",
        "name": "Antique Map",
        "style_label": "antique cartographic illustration",
        "style_description": (
            "aged parchment texture, hand-engraved linework, sepia and faded indigo palette, compass rose "
            "elements, sea monsters and ships in margins, Age-of-Exploration wonder"
        ),
        "notes": "Alexandria wildcard prompt. Antique map wonder with engraved exploratory drama.",
        "tags": ["alexandria", "wildcard", "antique-map", "cartographic", "scientific"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-maritime-chart",
        "name": "Maritime Chart",
        "style_label": "naval maritime illustration",
        "style_description": (
            "dramatic seascape composition, storm-grey and deep ocean-blue palette, copper-engraving linework, "
            "billowing sails and rigging detail, Turner-inspired atmospheric light on waves"
        ),
        "notes": "Alexandria wildcard prompt. Maritime chart drama with seafaring linework and storm light.",
        "tags": ["alexandria", "wildcard", "maritime-chart", "cartographic", "scientific"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-naturalist-field-drawing",
        "name": "Naturalist Field Drawing",
        "style_label": "Victorian naturalist field drawing",
        "style_description": (
            "precise pencil and watercolour, expedition-journal authenticity, warm sepia and olive green palette, "
            "scientific curiosity with artistic sensitivity, Audubon-inspired detail"
        ),
        "notes": "Alexandria wildcard prompt. Expedition-journal naturalism with observational precision.",
        "tags": ["alexandria", "wildcard", "naturalist-field-drawing", "cartographic", "scientific"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-painterly-soft",
        "name": "Painterly Soft Brushwork",
        "style_label": "hand-painted gouache and oil illustration",
        "style_description": (
            "visible brushwork texture on every surface, soft blended edges, atmospheric depth, warm light "
            "sources against cool shadows, layered pigment with soft dry-brush transitions"
        ),
        "prompt_template": (
            "Book cover illustration — no text, no lettering. Scene: {SCENE}. STYLE: Soft gouache and oil "
            "painting. Visible blended brushwork, soft edges, warm transitions, no hard lines. Muted earthy "
            "palette with gentle light. Dreamy atmospheric quality of vintage illustrated books. Mood: "
            "{MOOD}. Era: {ERA}. Every stroke must show the physical texture of hand-applied paint."
        ),
        "style_section": (
            "RENDERING TECHNIQUE: HAND-PAINTED illustration in gouache and oil painting style. MANDATORY "
            "visible brushwork texture on every surface — soft blended edges, NO hard vector lines, NO "
            "photorealism, NO 3D rendering, NO digital sharpness. Every element must look traditionally painted "
            "by hand. Atmospheric lighting with warm light sources blending into cool shadow areas. Color "
            "palette: deep midnight navy (#0a1628) for shadows and dark areas, warm burnished gold (#c5941a) "
            "and burnt amber (#cc7722) for all highlights and warm light, soft muted greens for any organic "
            "elements, dusty warm tones (#c08b7a) for skin. All surfaces must show visible brushstroke texture "
            "— layered pigment, soft dry-brush transitions, atmospheric depth between foreground and background. "
            "Composition uses cinematic depth: clear foreground subject, atmospheric middle ground, soft-focus "
            "painted background."
        ),
        "notes": "Alexandria wildcard prompt. Soft hand-painted gouache and oil brushwork with atmospheric depth.",
        "tags": ["alexandria", "wildcard", "painterly", "soft-brushwork", "gouache", "atmospheric"],
        "category": "wildcard",
    },
    {
        "id": "alexandria-wildcard-painterly-detailed",
        "name": "Painterly Hyper-Detailed",
        "style_label": "hand-painted hyper-detailed illustration",
        "style_description": (
            "meticulous individual rendering, saturated jewel-tone palette, golden-hour warmth, luminous light "
            "scatter, maximalist detail density with polished painterly finish"
        ),
        "prompt_template": (
            "Book cover illustration — no text, no lettering. Scene: {SCENE}. STYLE: Hyper-detailed "
            "hand-painted illustration. Meticulous brushwork on every fabric fold, architectural detail, and "
            "texture. Rich saturated colors, dense visual information across every inch. Museum-quality "
            "precision. Mood: {MOOD}. Era: {ERA}. Every stroke must show the physical texture of hand-applied paint."
        ),
        "style_section": (
            "RENDERING TECHNIQUE: HAND-PAINTED hyper-detailed digital painting with meticulously controlled "
            "painterly brushwork and METICULOUS individual rendering of every element — every fabric fold, every "
            "architectural detail, every natural texture must be individually painted with precision. Saturated "
            "jewel-tone color palette with golden-hour lighting warmth, NO photorealism, NO 3D rendering. Color "
            "palette: rich warm gold (#d4a017) and amber (#cc7722) for dominant warm light, deep cobalt blue "
            "(#0047ab) for sky and shadow areas, saturated emerald (#1a6b3a) for organic elements, rich crimson "
            "(#8b0000) and burgundy for warm accents, warm ivory (#f5e6c8) for illuminated surfaces. Light must "
            "glow and scatter — reflections on water, light through foliage, warm halos around light sources. "
            "Surface quality: highly polished and finished, smooth blending, NO visible canvas texture, every "
            "edge clean and precise. Maximalist detail density — the image should reward close inspection with "
            "ever-finer detail. Vibrant, luminous, jewel-like color saturation throughout."
        ),
        "notes": (
            "Alexandria wildcard prompt. Hyper-detailed painterly rendering with jewel-tone saturation and "
            "luminous finish."
        ),
        "tags": ["alexandria", "wildcard", "painterly", "hyper-detailed", "jewel-tone", "maximalist"],
        "category": "wildcard",
    },
)

ALEXANDRIA_PROMPT_SPECS: tuple[dict[str, object], ...] = tuple(
    {
        "id": str(spec["id"]),
        "name": str(spec["name"]),
        "prompt_template": str(spec.get("prompt_template") or _scene_first_prompt(
            str(spec["style_label"]),
            str(spec["style_description"]),
            style_section="",
            full_canvas=bool(spec.get("full_canvas")),
            texture_clause=_wildcard_texture_clause(str(spec["id"])),
        )),
        "negative_prompt": str(spec.get("negative_prompt") or ALEXANDRIA_BASE_NEGATIVE_PROMPT),
        "notes": str(spec["notes"]),
        "tags": list(spec["tags"]),
        "category": str(spec["category"]),
    }
    for spec in ALEXANDRIA_PROMPT_CATALOG
)

ALEXANDRIA_SCENE_FIRST_PROMPT_TEMPLATES: dict[str, str] = {
    str(spec["id"]): str(spec["prompt_template"])
    for spec in ALEXANDRIA_PROMPT_SPECS
}


@dataclass(slots=True)
class StyleAnchor:
    """A reusable style component that can be mixed into prompts."""

    name: str
    description: str
    style_text: str
    tags: list[str]


@dataclass(slots=True)
class LibraryPrompt:
    """A saved prompt that worked well."""

    id: str
    name: str
    prompt_template: str
    style_anchors: list[str]
    negative_prompt: str
    source_book: str
    source_model: str
    quality_score: float
    saved_by: str
    created_at: str
    notes: str
    tags: list[str]
    category: str = "general"
    version: int = 1
    usage_count: int = 0
    win_count: int = 0
    last_used_at: str = ""
    updated_at: str = ""


class PromptLibrary:
    """Manages style anchors and saved prompts for single-cover iteration and bulk runs."""

    def __init__(self, library_path: Path):
        self.library_path = library_path
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        self._style_anchors: dict[str, StyleAnchor] = {}
        self._prompts: dict[str, LibraryPrompt] = {}
        self._versions: dict[str, list[dict[str, object]]] = {}
        self._load_or_seed()

    def get_style_anchors(self) -> list[StyleAnchor]:
        """Return all available style anchors."""
        return sorted(self._style_anchors.values(), key=lambda anchor: anchor.name)

    def save_prompt(self, prompt: LibraryPrompt) -> None:
        """Save a successful prompt to the library."""
        category = str(getattr(prompt, "category", "general") or "general")
        _validate_prompt_template(prompt.prompt_template, category=category)
        existing = self._prompts.get(prompt.id)
        normalized = LibraryPrompt(
            id=str(prompt.id),
            name=str(prompt.name or prompt.id),
            prompt_template=str(prompt.prompt_template),
            style_anchors=[str(anchor).strip() for anchor in list(prompt.style_anchors)],
            negative_prompt=str(prompt.negative_prompt or ""),
            source_book=str(prompt.source_book or ""),
            source_model=str(prompt.source_model or ""),
            quality_score=float(prompt.quality_score or 0.0),
            saved_by=str(prompt.saved_by or "auto"),
            created_at=str(prompt.created_at or _utc_now()),
            notes=str(prompt.notes or ""),
            tags=[str(tag).strip() for tag in list(prompt.tags)],
            category=category,
            version=max(1, int(getattr(prompt, "version", 1) or 1)),
            usage_count=max(0, int(getattr(prompt, "usage_count", 0) or 0)),
            win_count=max(0, int(getattr(prompt, "win_count", 0) or 0)),
            last_used_at=str(getattr(prompt, "last_used_at", "") or ""),
            updated_at=str(getattr(prompt, "updated_at", "") or _utc_now()),
        )
        if existing is not None:
            history = self._versions.setdefault(str(prompt.id), [])
            history.append(asdict(existing))
            normalized.version = max(1, int(existing.version or 1) + 1)
            if len(history) > 100:
                del history[:-100]
        self._prompts[prompt.id] = normalized
        self._persist()
        logger.info(
            "Saved prompt to library",
            extra={"prompt_id": prompt.id, "prompt_name": prompt.name, "score": prompt.quality_score},
        )

    def get_prompts(self, tags: list[str] | None = None) -> list[LibraryPrompt]:
        """Get prompts, optionally filtered by tags."""
        values = list(self._prompts.values())
        if tags:
            wanted = {tag.strip().lower() for tag in tags if tag.strip()}
            values = [
                prompt
                for prompt in values
                if wanted.intersection({tag.lower() for tag in prompt.tags})
                or wanted.intersection({anchor.lower() for anchor in prompt.style_anchors})
            ]
        return _sorted_prompts(values)

    def get_prompt(self, prompt_id: str) -> LibraryPrompt | None:
        """Return one prompt by id."""
        return self._prompts.get(str(prompt_id))

    def find_prompt_by_template_text(self, prompt_text: str) -> LibraryPrompt | None:
        """Return one prompt whose stored text matches after whitespace normalization."""
        target = _normalize_prompt_text(prompt_text)
        if not target:
            return None
        for prompt in self._prompts.values():
            if _normalize_prompt_text(prompt.prompt_template) == target:
                return prompt
        return None

    def get_versions(self, prompt_id: str) -> list[dict[str, object]]:
        """Return historical versions for one prompt id."""
        rows = self._versions.get(str(prompt_id), [])
        return list(rows)

    def update_prompt(self, prompt_id: str, **updates: object) -> LibraryPrompt:
        """Update one prompt and persist previous state to versions history."""
        token = str(prompt_id)
        current = self._prompts.get(token)
        if current is None:
            raise KeyError(prompt_id)

        history = self._versions.setdefault(token, [])
        history.append(asdict(current))
        if len(history) > 100:
            del history[:-100]

        name = str(updates.get("name", current.name) or current.name).strip() or current.name
        prompt_template = str(updates.get("prompt_template", current.prompt_template) or current.prompt_template).strip() or current.prompt_template
        target_category = str(updates.get("category", current.category) or current.category or "general")
        _validate_prompt_template(prompt_template, category=target_category)

        style_anchors = updates.get("style_anchors", current.style_anchors)
        tags = updates.get("tags", current.tags)
        updated = LibraryPrompt(
            id=current.id,
            name=name,
            prompt_template=prompt_template,
            style_anchors=[str(anchor).strip() for anchor in style_anchors] if isinstance(style_anchors, list) else list(current.style_anchors),
            negative_prompt=str(updates.get("negative_prompt", current.negative_prompt) or current.negative_prompt),
            source_book=str(updates.get("source_book", current.source_book) or current.source_book),
            source_model=str(updates.get("source_model", current.source_model) or current.source_model),
            quality_score=float(updates.get("quality_score", current.quality_score) or current.quality_score),
            saved_by=str(updates.get("saved_by", current.saved_by) or current.saved_by),
            created_at=current.created_at,
            notes=str(updates.get("notes", current.notes) or current.notes),
            tags=[str(tag).strip() for tag in tags] if isinstance(tags, list) else list(current.tags),
            category=target_category,
            version=max(1, int(current.version or 1) + 1),
            usage_count=max(0, int(updates.get("usage_count", current.usage_count) or current.usage_count)),
            win_count=max(0, int(updates.get("win_count", current.win_count) or current.win_count)),
            last_used_at=str(updates.get("last_used_at", current.last_used_at) or current.last_used_at),
            updated_at=_utc_now(),
        )
        self._prompts[token] = updated
        self._persist()
        return updated

    def delete_prompt(self, prompt_id: str) -> bool:
        """Delete one prompt by id."""
        token = str(prompt_id)
        if token not in self._prompts:
            return False
        self._prompts.pop(token, None)
        self._versions.pop(token, None)
        self._persist()
        return True

    def record_usage(self, prompt_id: str, *, won: bool = False) -> LibraryPrompt:
        """Increment usage and optional win counters for one prompt."""
        token = str(prompt_id)
        current = self._prompts.get(token)
        if current is None:
            raise KeyError(prompt_id)
        updated = LibraryPrompt(
            id=current.id,
            name=current.name,
            prompt_template=current.prompt_template,
            style_anchors=list(current.style_anchors),
            negative_prompt=current.negative_prompt,
            source_book=current.source_book,
            source_model=current.source_model,
            quality_score=current.quality_score,
            saved_by=current.saved_by,
            created_at=current.created_at,
            notes=current.notes,
            tags=list(current.tags),
            category=current.category,
            version=max(1, int(current.version or 1)),
            usage_count=max(0, int(current.usage_count or 0) + 1),
            win_count=max(0, int(current.win_count or 0) + (1 if won else 0)),
            last_used_at=_utc_now(),
            updated_at=_utc_now(),
        )
        self._prompts[token] = updated
        self._persist()
        return updated

    def search_prompts(
        self,
        query: str = "",
        tags: Sequence[str] | None = None,
        min_quality: float = 0.0,
    ) -> list[LibraryPrompt]:
        """Search prompts by text, tags, and minimum quality score."""
        query_tokens = {token for token in query.lower().split() if token}
        tag_tokens = {token.lower() for token in tags} if tags else set()

        def _matches(prompt: LibraryPrompt) -> bool:
            if prompt.quality_score < min_quality:
                return False

            blob = " ".join(
                [
                    prompt.name,
                    prompt.prompt_template,
                    prompt.notes,
                    " ".join(prompt.tags),
                    " ".join(prompt.style_anchors),
                ]
            ).lower()

            if query_tokens and not all(token in blob for token in query_tokens):
                return False

            if tag_tokens:
                prompt_tokens = {tag.lower() for tag in prompt.tags}.union(
                    {anchor.lower() for anchor in prompt.style_anchors}
                )
                if not tag_tokens.intersection(prompt_tokens):
                    return False
            return True

        return _sorted_prompts(prompt for prompt in self._prompts.values() if _matches(prompt))

    def build_prompt(self, book_title: str, style_anchors: list[str], custom_text: str = "") -> str:
        """Build a prompt from style anchors + book title + optional custom text."""
        selected = [self._style_anchors[name] for name in style_anchors if name in self._style_anchors]
        if not selected:
            raise ValueError("At least one valid style anchor is required to build a prompt.")

        style_text = ", ".join(anchor.style_text for anchor in selected)
        custom_part = f" {custom_text.strip()}" if custom_text.strip() else ""
        prompt = (
            f"Create a circular medallion illustration for \"{book_title}\" showing the most iconic "
            f"scene or symbolic moment from the story.{custom_part} {style_text}"
        )
        return " ".join(prompt.split())

    def get_best_prompts_for_bulk(self, top_n: int = 5) -> list[LibraryPrompt]:
        """Get top-N prompts by quality score for bulk processing."""
        ordered = sorted(self._prompts.values(), key=lambda prompt: prompt.quality_score, reverse=True)
        return ordered[: max(1, top_n)]

    def add_style_anchor(self, anchor: StyleAnchor) -> None:
        """Add or update a style anchor."""
        self._style_anchors[anchor.name] = anchor
        self._persist()
        logger.info("Upserted style anchor", extra={"anchor": anchor.name})

    def _load_or_seed(self) -> None:
        changed = False
        if self.library_path.exists():
            self._load()
            changed = self._ensure_alexandria_prompts() or changed
            if self._style_anchors and self._prompts:
                if changed:
                    self._persist()
                return

        anchors, prompts = self._seed_library()
        self._style_anchors = {anchor.name: anchor for anchor in anchors}
        self._prompts = {prompt.id: prompt for prompt in prompts}
        self._ensure_alexandria_prompts()
        self._persist()

    def _load(self) -> None:
        payload = safe_json.load_json(self.library_path, {})
        if not isinstance(payload, dict):
            payload = {}
        style_payload = payload.get("style_anchors", [])
        prompts_payload = payload.get("prompts", [])

        anchors: dict[str, StyleAnchor] = {}
        for item in style_payload if isinstance(style_payload, list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            tags_raw = item.get("tags", [])
            tags = [str(tag).strip() for tag in tags_raw] if isinstance(tags_raw, list) else []
            anchors[name] = StyleAnchor(
                name=name,
                description=str(item.get("description", "")).strip(),
                style_text=str(item.get("style_text", "")).strip(),
                tags=[tag for tag in tags if tag],
            )
        self._style_anchors = anchors

        prompts: dict[str, LibraryPrompt] = {}
        for item in prompts_payload if isinstance(prompts_payload, list) else []:
            if not isinstance(item, dict):
                continue
            prompt_id = str(item.get("id", "")).strip()
            template = str(item.get("prompt_template", "")).strip()
            if not prompt_id or not template:
                continue
            style_raw = item.get("style_anchors", [])
            tags_raw = item.get("tags", [])
            prompts[prompt_id] = LibraryPrompt(
                id=prompt_id,
                name=str(item.get("name", "")).strip() or prompt_id,
                prompt_template=template,
                style_anchors=[str(anchor).strip() for anchor in style_raw] if isinstance(style_raw, list) else [],
                negative_prompt=str(item.get("negative_prompt", "")).strip(),
                source_book=str(item.get("source_book", "")).strip(),
                source_model=str(item.get("source_model", "")).strip(),
                quality_score=float(item.get("quality_score", 0.0) or 0.0),
                saved_by=str(item.get("saved_by", "auto") or "auto"),
                created_at=str(item.get("created_at", _utc_now()) or _utc_now()),
                notes=str(item.get("notes", "")).strip(),
                tags=[str(tag).strip() for tag in tags_raw] if isinstance(tags_raw, list) else [],
                category=str(item.get("category", "general") or "general"),
                version=max(1, int(item.get("version", 1) or 1)),
                usage_count=max(0, int(item.get("usage_count", 0) or 0)),
                win_count=max(0, int(item.get("win_count", 0) or 0)),
                last_used_at=str(item.get("last_used_at", "") or ""),
                updated_at=str(item.get("updated_at", "") or ""),
            )
        self._prompts = prompts

        versions_payload = payload.get("versions", {})
        versions: dict[str, list[dict[str, object]]] = {}
        if isinstance(versions_payload, dict):
            for key, rows in versions_payload.items():
                if not isinstance(rows, list):
                    continue
                cleaned = [dict(item) for item in rows if isinstance(item, dict)]
                if cleaned:
                    versions[str(key)] = cleaned[-100:]
        self._versions = versions

    def _persist(self) -> None:
        payload = {
            "version": 2,
            "updated_at": _utc_now(),
            "style_anchors": [asdict(anchor) for anchor in self.get_style_anchors()],
            "prompts": [
                asdict(prompt)
                for prompt in _sorted_prompts(self._prompts.values())
            ],
            "versions": {prompt_id: rows for prompt_id, rows in self._versions.items()},
        }
        safe_json.atomic_write_json(self.library_path, payload)
        logger.debug("Persisted prompt library", extra={"path": str(self.library_path), "anchors": len(self._style_anchors), "prompts": len(self._prompts)})

    def _ensure_alexandria_prompts(self) -> bool:
        changed = False
        existing_by_name = {str(prompt.name).strip().lower(): prompt for prompt in self._prompts.values()}
        for spec in ALEXANDRIA_PROMPT_SPECS:
            prompt_id = str(spec.get("id", "")).strip()
            name = str(spec.get("name", "")).strip()
            target_template = ALEXANDRIA_SCENE_FIRST_PROMPT_TEMPLATES.get(
                prompt_id,
                str(spec.get("prompt_template", "")).strip(),
            )
            target_negative_prompt = str(spec.get("negative_prompt") or ALEXANDRIA_SYSTEM_NEGATIVE_PROMPT).strip()
            target_notes = str(spec.get("notes", "")).strip()
            target_tags = list(spec.get("tags", [])) if isinstance(spec.get("tags", []), list) else ["alexandria"]
            target_category = str(spec.get("category", "builtin") or "builtin").strip()
            if not prompt_id or not name:
                continue
            current = self._prompts.get(prompt_id) or existing_by_name.get(name.lower())
            if current is not None:
                current_changed = False
                if str(current.name or "").strip() != name:
                    current.name = name
                    current_changed = True
                if str(current.prompt_template or "").strip() != target_template:
                    current.prompt_template = target_template
                    current_changed = True
                if str(current.notes or "").strip() != target_notes:
                    current.notes = target_notes
                    current_changed = True
                if list(current.tags or []) != target_tags:
                    current.tags = list(target_tags)
                    current_changed = True
                if str(current.category or "").strip() != target_category:
                    current.category = target_category
                    current_changed = True
                if str(current.negative_prompt or "").strip() != target_negative_prompt:
                    current.negative_prompt = target_negative_prompt
                    current_changed = True
                if str(current.source_book or "").strip() != "builtin":
                    current.source_book = "builtin"
                    current_changed = True
                if str(current.source_model or "").strip() != "openrouter/google/gemini-3-pro-image-preview":
                    current.source_model = "openrouter/google/gemini-3-pro-image-preview"
                    current_changed = True
                if current_changed:
                    current.updated_at = _utc_now()
                    self._prompts[current.id] = current
                    changed = True
                continue
            created_at = _utc_now()
            prompt = LibraryPrompt(
                id=prompt_id,
                name=name,
                prompt_template=target_template,
                style_anchors=[],
                negative_prompt=target_negative_prompt,
                source_book="builtin",
                source_model="openrouter/google/gemini-3-pro-image-preview",
                quality_score=1.0,
                saved_by="system",
                created_at=created_at,
                notes=target_notes,
                tags=target_tags,
                category=target_category,
                version=1,
                usage_count=0,
                win_count=0,
                last_used_at="",
                updated_at=created_at,
            )
            self._prompts[prompt.id] = prompt
            existing_by_name[name.lower()] = prompt
            changed = True
        return changed

    def _seed_library(self) -> tuple[list[StyleAnchor], list[LibraryPrompt]]:
        templates = safe_json.load_json(config.PROMPT_TEMPLATES_PATH, {})
        if not isinstance(templates, dict):
            templates = {}
        negative_prompt = templates.get("negative_prompt", "")

        style_groups = templates.get("style_groups", {})
        sketch_text = style_groups.get("sketch_style", {}).get("style_anchors", "")
        oil_text = style_groups.get("oil_painting_style", {}).get("style_anchors", "")
        alt_text = style_groups.get("alternative_style", {}).get("style_anchors", "")

        anchors = [
            StyleAnchor(
                name="warm_sepia_sketch",
                description="Hand-drawn 19th-century sketch aesthetic with sepia warmth.",
                style_text=sketch_text or "classical pen-and-ink sketch, sepia tones, crosshatching",
                tags=["sketch", "sepia", "classical"],
            ),
            StyleAnchor(
                name="engraving_detailed",
                description="Ultra-detailed copperplate engraving and etching line work.",
                style_text="copper plate engraving, fine line work, meticulous etching detail, circular vignette composition",
                tags=["engraving", "detailed", "linework"],
            ),
            StyleAnchor(
                name="dramatic_oil",
                description="Classical oil painting with dramatic light and depth.",
                style_text=oil_text or "classical oil painting, dramatic chiaroscuro, rich brushwork",
                tags=["oil", "dramatic", "classical"],
            ),
            StyleAnchor(
                name="gothic_moody",
                description="Dark romantic mood with atmospheric shadows.",
                style_text="gothic romantic atmosphere, moody shadows, dramatic rim lighting, painterly depth",
                tags=["gothic", "moody", "dramatic"],
            ),
            StyleAnchor(
                name="watercolor_soft",
                description="Soft watercolor washes with delicate transitions.",
                style_text="soft watercolor washes, delicate brush texture, gentle tonal transitions, classical composition",
                tags=["watercolor", "soft", "pastoral"],
            ),
            StyleAnchor(
                name="allegorical_symbolic",
                description="Symbolic visual storytelling with period-appropriate motifs.",
                style_text=alt_text or "period-appropriate artistic style, allegorical symbolism, hand-crafted aesthetic",
                tags=["symbolic", "allegory", "alternative"],
            ),
        ]

        starter_prompt_specs = [
            {
                "name": "Iconic Scene Sketch Baseline",
                "template": "Detailed pen-and-ink engraving of the most iconic scene from {title}, rendered as a circular vignette.",
                "anchors": ["warm_sepia_sketch", "engraving_detailed"],
                "model": "flux-2-pro",
                "score": 0.80,
                "tags": ["iconic", "sketch", "baseline"],
                "notes": "Strong baseline for classical literary titles.",
            },
            {
                "name": "Character Portrait Etching",
                "template": "Classical engraved portrait of the central character from {title}, with expressive posture and period costume.",
                "anchors": ["warm_sepia_sketch", "engraving_detailed"],
                "model": "gpt-image-1-medium",
                "score": 0.78,
                "tags": ["portrait", "character", "sketch"],
                "notes": "Works well when character focus is more recognizable than scene focus.",
            },
            {
                "name": "Setting-Led Sketch Landscape",
                "template": "19th-century style book illustration of the defining setting from {title}, emphasizing depth and architectural detail.",
                "anchors": ["warm_sepia_sketch", "engraving_detailed"],
                "model": "flux-2-schnell",
                "score": 0.73,
                "tags": ["setting", "landscape", "sketch"],
                "notes": "Fast and cheap exploration pattern for geography-heavy books.",
            },
            {
                "name": "Dramatic Chiaroscuro Moment",
                "template": "Masterpiece-style classical oil painting of the pivotal dramatic moment in {title}, with cinematic light contrast.",
                "anchors": ["dramatic_oil"],
                "model": "gpt-image-1-high",
                "score": 0.84,
                "tags": ["dramatic", "oil", "high_quality"],
                "notes": "High-end quality ceiling prompt for shortlist comparisons.",
            },
            {
                "name": "Gothic Tension Scene",
                "template": "Atmospheric gothic interpretation of the most psychologically intense moment from {title}.",
                "anchors": ["dramatic_oil", "gothic_moody"],
                "model": "imagen-4-ultra",
                "score": 0.81,
                "tags": ["gothic", "mood", "dramatic"],
                "notes": "Useful for darker classics and tragic narratives.",
            },
            {
                "name": "Soft Symbolic Watercolor",
                "template": "Symbolic watercolor composition for {title}, using allegorical objects to represent the book's core themes.",
                "anchors": ["watercolor_soft", "allegorical_symbolic"],
                "model": "imagen-4-fast",
                "score": 0.75,
                "tags": ["symbolic", "watercolor", "alternative"],
                "notes": "Good fallback when literal scenes feel crowded inside circular crops.",
            },
            {
                "name": "Baroque Allegory",
                "template": "Classical allegorical illustration for {title}, with period motifs and layered symbolic storytelling.",
                "anchors": ["allegorical_symbolic", "engraving_detailed"],
                "model": "nano-banana-pro",
                "score": 0.76,
                "tags": ["allegory", "symbolic", "baroque"],
                "notes": "Balances uniqueness with consistency for batch candidates.",
            },
            {
                "name": "Heroic Oil Tableau",
                "template": "Heroic classical oil tableau depicting the defining confrontation from {title}, with rich golden highlights.",
                "anchors": ["dramatic_oil"],
                "model": "flux-2-pro",
                "score": 0.79,
                "tags": ["heroic", "oil", "tableau"],
                "notes": "Performs well on action-driven works.",
            },
            {
                "name": "Etching with Narrative Depth",
                "template": "Dense copperplate-style etching of a narrative turning point from {title}, emphasizing layered storytelling details.",
                "anchors": ["engraving_detailed", "warm_sepia_sketch"],
                "model": "gpt-image-1-medium",
                "score": 0.82,
                "tags": ["etching", "detail", "narrative"],
                "notes": "Reliable prompt for rich compositions with many micro-details.",
            },
            {
                "name": "Painterly Pastoral Variant",
                "template": "Pastoral yet classical rendering of a key emotional scene from {title}, favoring gentle brushwork over hard outlines.",
                "anchors": ["watercolor_soft", "dramatic_oil"],
                "model": "imagen-4-fast",
                "score": 0.74,
                "tags": ["pastoral", "painterly", "variant"],
                "notes": "Adds tonal diversity while staying aligned with the cover aesthetic.",
            },
        ]

        prompts = [
            LibraryPrompt(
                id=str(uuid.uuid4()),
                name=item["name"],
                prompt_template=item["template"],
                style_anchors=list(item["anchors"]),
                negative_prompt=negative_prompt,
                source_book="Moby Dick",
                source_model=item["model"],
                quality_score=float(item["score"]),
                saved_by="auto",
                created_at=_utc_now(),
                notes=item["notes"],
                tags=list(item["tags"]),
            )
            for item in starter_prompt_specs
        ]

        return anchors, prompts



def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_prompt_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _category_allows_plain_prompt(category: str) -> bool:
    return str(category or "").strip().lower() == "winner"


def _validate_prompt_template(template: str, *, category: str = "general") -> None:
    normalized = _normalize_prompt_text(template)
    if not normalized:
        raise ValueError("Prompt template must not be empty.")
    if _category_allows_plain_prompt(category):
        return
    if not _has_supported_placeholder(normalized):
        joined = ", ".join(SUPPORTED_REUSABLE_PLACEHOLDERS)
        raise ValueError(f"Prompt template must include at least one reusable placeholder ({joined}).")


def _has_supported_placeholder(template: str) -> bool:
    token = str(template or "")
    return any(marker in token for marker in SUPPORTED_REUSABLE_PLACEHOLDERS)


def _prompt_priority(prompt: LibraryPrompt) -> tuple[int, int, float, int, int, str]:
    tags = {str(tag).strip().lower() for tag in prompt.tags if str(tag).strip()}
    is_alexandria = 1 if "alexandria" in tags else 0
    is_builtin = 1 if str(prompt.category or "").strip().lower() == "builtin" else 0
    return (
        is_alexandria,
        is_builtin,
        float(prompt.quality_score or 0.0),
        int(prompt.win_count or 0),
        int(prompt.usage_count or 0),
        str(prompt.created_at or ""),
    )


def _sorted_prompts(prompts: Iterable[LibraryPrompt]) -> list[LibraryPrompt]:
    return sorted(prompts, key=_prompt_priority, reverse=True)


def load_default_prompt_library() -> PromptLibrary:
    """Load prompt library from default project location."""
    return PromptLibrary(config.PROMPT_LIBRARY_PATH)


def build_prompt_from_anchors(book_title: str, anchors: Iterable[str], custom_text: str = "") -> str:
    """Convenience wrapper for ad-hoc prompt creation."""
    library = load_default_prompt_library()
    return library.build_prompt(book_title=book_title, style_anchors=list(anchors), custom_text=custom_text)
