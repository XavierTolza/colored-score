# 🎼 Colored-Score

> Transforme des partitions en notation **ABC** en partitions **PDF visuelles et
> colorées**, où chaque note adopte la couleur de la touche correspondante du
> clavier **Baby Einstein / Hape** (8 touches, Do4 → Do5).

![Statut](https://img.shields.io/badge/python-3.9%2B-blue)
![Licence](https://img.shields.io/badge/licence-MIT-green)
![PDF](https://img.shields.io/badge/export-PDF-red)

---

## 📖 Sommaire

1. [Présentation](#-présentation)
2. [Code couleur du clavier](#-code-couleur-du-clavier)
3. [Aperçu du rendu](#-aperçu-du-rendu)
4. [Prérequis & installation](#-prérequis--installation)
5. [Guide d'utilisation](#-guide-dutilisation)
6. [Personnalisation (formats, tailles, marges)](#-personnalisation-formats-tailles-marges)
7. [Format ABC supporté](#-format-abc-supporté)
8. [Publication automatique sur GitHub](#-publication-automatique-sur-github)
9. [Architecture du projet](#-architecture-du-projet)
10. [Tests](#-tests)
11. [Licences & crédits](#-licences--crédits)

---

## 🎯 Présentation

**Colored-Score** lit une partition au format texte **ABC notation**, la filtre
et la valide pour la **gamme de 8 notes** présente sur le clavier du piano jouet
Baby Einstein / Hape (Do4 à Do5), puis génère un **document PDF imprimable**
sur lequel :

- une **portée classique en clé de sol** est dessinée ;
- chaque note est **colorée** selon la correspondance stricte du clavier ;
- une **légende** rappelle le mapping notes/couleurs ;
- et **toute la mise en page est paramétrable** via un fichier `config.yaml`
  (format de papier, marges, taille des notes, interlignes, titre, ...).

Le projet inclut également `publish_github.py`, un outil d'automatisation
DevOps qui **crée un dépôt GitHub, l'initialise, le commite et le pousse**
en une seule commande.

---

## 🎨 Code couleur du clavier

Correspondance **stricte** et dans l'ordre physique des touches (de gauche à
droite), implémentée dans `config.yaml` :

| # | Note (FR) | Note (EN) | Octave | Notation ABC | Couleur | Hex |
|---|-----------|-----------|:------:|:------------:|:-------:|-----|
| 1 | **Do**  | C4 | 4 | `C` | 🔴 Rouge           | `#E51937` |
| 2 | **Ré**  | D4 | 4 | `D` | 🟠 Orange          | `#F37023` |
| 3 | **Mi**  | E4 | 4 | `E` | 🟡 Jaune           | `#FFD100` |
| 4 | **Fa**  | F4 | 4 | `F` | 🟢 Vert            | `#5BB847` |
| 5 | **Sol** | G4 | 4 | `G` | 🔵 Bleu clair      | `#00AEEF` |
| 6 | **La**  | A4 | 4 | `A` | 🔵 Bleu foncé      | `#0054A6` |
| 7 | **Si**  | B4 | 4 | `B` | 🟣 Violet / Rose   | `#B552A0` |
| 8 | **Do**  | C5 | 5 | `c` | 🔴 Rouge / Magenta | `#D81B60` |

> Les notes hors de cette gamme sont ramenées dans l'octave correspondante selon
> la politique configurable `policy.out_of_range` (`transpose`, `skip` ou
> `error`). Voir [Personnalisation](#-personnalisation-formats-tailles-marges).

---

## 🖼️ Aperçu du rendu

Exemple généré depuis `samples/la_gamme_complete.pdf` (gamme complète Do→Do) :

```
  𝄞  ♪ ♪ ♪ ♪ ♪ ♪ ♪ ♪  |  ♪ ♪ ♪ ♪ ♪ ♪ ♪ ♪  |
    Do Ré Mi Fa Sol La Si Do   ...
   [clavier coloré en légende : 8 touches Do4 → Do5]
```

Pour visualiser un rendu réel, générez l'un des exemples fournis :

```bash
python main.py samples/la_gamme_complete.abc   # -> output/la_gamme_complete.pdf
```

---

## ⚙️ Prérequis & installation

### Prérequis

- **Python 3.9** ou supérieur
- Git (pour la publication GitHub)

### Installation

```bash
# 1. Cloner (ou copier) le projet
git clone <votre-depot> colored-score
cd colored-score

# 2. (recommandé) Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate

# 3. Installer les dépendances
pip install -r requirements.txt
```

### (Optionnel) Régénérer la police musicale

La fonte musicale [Bravura](https://github.com/steinbergmedia/bravura) (SMuFL,
licence OFL) est fournie dans `assets/`. Le fichier `Bravura.ttf` (contours
TrueType, requis par ReportLab) est **déjà versionné**. Si vous devez le
régénérer :

```bash
python tools/build_font.py
```

---

## 🚀 Guide d'utilisation

### Générer un PDF à partir d'un fichier ABC

```bash
python main.py samples/ode_a_la_joie.abc
# -> écrit output/ode_a_la_joie.pdf
```

### Spécifier le fichier de sortie

```bash
python main.py samples/gamme.abc -o output/ma_gamme.pdf
```

### Générer tous les exemples d'un dossier

```bash
python main.py --all                       # dossier samples/ par défaut
python main.py --all --samples-dir mes_abc # dossier personnalisé
```

### Utiliser une configuration alternative

```bash
python main.py samples/gamme.abc --config config_a5.yaml
```

### Aide en ligne de commande

```bash
python main.py --help
```

### Utilisation comme bibliothèque

```python
from config import load_config
from abc_parser import load_abc_file
from pdf_generator import PDFGenerator

cfg = load_config("config.yaml")
score = load_abc_file("samples/gamme.abc", cfg)
PDFGenerator(cfg).generate(score, "output/resultat.pdf")
```

---

## 🎛️ Personnalisation (formats, tailles, marges)

Tout se règle dans **`config.yaml`**. Les principales sections :

### Format de page

```yaml
layout:
  page_size: "A4"          # A3, A4, A5, A6, LETTER, LEGAL
  orientation: "portrait"  # portrait | landscape
  margins:                 # en millimètres
    top: 20
    bottom: 20
    left: 15
    right: 15
```

### Dimensions des portées et des notes

```yaml
layout:
  staff:
    space: 3.2             # interligne (écart entre 2 lignes) en mm
    line_width: 0.8        # épaisseur des lignes de portée (pt)
    system_gap: 20.0       # espace entre deux systèmes (mm)
  notes_style:
    spacing: 9.0           # espace horizontal entre deux notes (mm)
    stem_length: 3.4       # longueur de la hampe (interlignes)
    ledger_length: 5.4     # longueur des lignes supplémentaires (mm)
    show_labels: true      # afficher Do, Ré, Mi... sous chaque note
    label_font_size: 8
    label_offset: 9.0      # décalage vertical du libellé (mm)
```

### Titre & légende

```yaml
layout:
  title:
    font_size: 22
    spacing_after: 4
  legend:
    enabled: true
    title: "Légende du clavier (8 touches)"
    key_width: 12.0
    key_height: 18.0
```

### Couleurs du clavier

Pour ajuster une nuance, modifiez la clé `color` de la note concernée :

```yaml
notes:
  C: { name: "Do", octave: 4, order: 1, color: "#E51937", label_en: "C4" }
  # ...
  c: { name: "Do", octave: 5, order: 8, color: "#D81B60", label_en: "C5" }
```

### Politique des notes hors gamme

```yaml
policy:
  out_of_range: "transpose"  # transpose | skip | error
```

| Valeur      | Comportement |
|-------------|--------------|
| `transpose` | Replie l'octave / rapproche la touche la plus proche (défaut) |
| `skip`      | Ignore la note (silence) |
| `error`     | Lève une exception explicite |

---

## 🎵 Format ABC supporté

Le parseur est volontairement **ciblé** sur des mélodies simples monophoniques.
En-têtes reconnus : `X`, `T`, `C`, `M`, `L`, `K`, `Q`.

**Fichier d'exemple (`samples/ode_a_la_joie.abc`) :**

```abc
X:1
T:Ode à la Joie
C:Ludwig van Beethoven
M:4/4
L:1/4
K:C
E E F G | G F E D | C C D E | E D D2 |
E E F G | G F E D | C C D E | D C C2 |]
```

| Élément ABC | Interprétation |
|-------------|----------------|
| `C`, `D`, ... `B` | Notes de l'octave 4 (Do4 .. Si4) |
| `c` | Do5 (lettre minuscule = octave supérieure) |
| `z`, `x` | Silences |
| `|`, `||`, `|]`, `:|`, `|:` | Barres de mesure |
| `2`, `3`, `/`, `3/2` | Durées (relatives à `L:`) |
| `("Am")`, `%...` | Accords et commentaires ignorés |

> **Note :** les altérations (`^`, `_`) sont acceptées mais ramenées à la touche
> diatonique la plus proche, car le clavier ne comporte que des touches blanches.

---

## 🚢 Publication automatique sur GitHub

Le script **`publish_github.py`** réalise tout le cycle DevOps :

1. **Création** du dépôt distant (public ou privé) via l'API GitHub ;
2. **`git init`** du dépôt local ;
3. **Commit** de l'ensemble du projet ;
4. **Push** sur la branche `main` du dépôt distant.

### 1. Créer un Personal Access Token (PAT)

1. Connectez-vous à GitHub : **Settings → Developer settings →
   Personal access tokens → Tokens (classic)**.
2. Cliquez **Generate new token (classic)**.
3. Nommez-le (ex. `colored-score-publish`) et cochez la portée **`repo`**
   (indispensable pour créer un dépôt et pousser du code).
4. Générez et **copiez** le token (`ghp_...`).

> Alternative fine-grained : créez un token avec les permissions
> *Repository → Administration (write)* et *Contents (write)*.

### 2. Exporter le token

```bash
export GITHUB_TOKEN=ghp_votreTokenIci          # Linux / macOS
# PowerShell :
$env:GITHUB_TOKEN = "ghp_votreTokenIci"
```

### 3. Publier

```bash
# Dépôt public
python publish_github.py --repo-name colored-score --public

# Dépôt privé (défaut) avec description
python publish_github.py --repo-name colored-score --private \
    --description "Partitions colorées façon clavier Baby Einstein"

# Branche personnalisée
python publish_github.py --repo-name colored-score --public --branch main
```

À la fin, le script affiche l'URL du dépôt :

```
[pub] Terminé -> https://github.com/<votre-login>/colored-score
```

### Paramètres disponibles

| Option | Description |
|--------|-------------|
| `--repo-name` | **Requis.** Nom du dépôt distant |
| `--public` / `--private` | Visibilité (privé par défaut) |
| `--description` | Description du dépôt |
| `--branch` | Branche principale (défaut : `main`) |
| `--dir` | Répertoire local à publier (défaut : `.`) |
| `--message` | Message du commit initial |
| `--token` | PAT explicite (sinon variable `GITHUB_TOKEN`) |

> 🔐 **Sécurité :** le token n'est **jamais** écrit sur disque. L'URL
> authentifiée n'est utilisée que pour le `push`. Pensez à
> **révoquer** le token s'il a pu être exposé.

---

## 🏗️ Architecture du projet

```
colored-score/
├── config.yaml            # ⚙️ Configuration centrale (notes, couleurs, layout)
├── config.py              # Chargement + validation typée de la config
├── abc_parser.py          # Parsing / filtrage / validation des partitions ABC
├── pdf_generator.py       # Moteur de rendu graphique et export PDF
├── bravura.py             # Accès à la fonte musicale Bravura (SMuFL)
├── main.py                # 🚀 Point d'entrée de l'application
├── publish_github.py      # 📤 Publication automatique sur GitHub
├── requirements.txt       # Dépendances Python
├── .gitignore             # Exclusions Git (projet Python)
├── assets/
│   ├── Bravura.otf        # Fonte musicale source (SMuFL, OFL)
│   └── Bravura.ttf        # Fonte convertie TrueType (utilisée par ReportLab)
├── samples/
│   ├── frere_jacques.abc
│   ├── ode_a_la_joie.abc
│   ├── au_clair_de_la_lune.abc
│   ├── happy_birthday.abc
│   └── gamme.abc
├── tests/
│   ├── test_abc_parser.py
│   ├── test_config.py
│   └── test_pdf_generator.py
├── tools/
│   └── build_font.py      # Conversion OTF -> TTF de la fonte Bravura
└── output/                # PDF générés (non versionné)
```

### Rôle des modules

| Module | Responsabilité |
|--------|----------------|
| `config.py` | Charge `config.yaml`, valide couleurs/format et expose `ScoreConfig` |
| `abc_parser.py` | Transforme le texte ABC en événements (`NoteEvent`, `BarEvent`) sur la gamme Do4–Do5 |
| `pdf_generator.py` | Dessine portée, clé, notes colorées, barres, légende ; gère la pagination |
| `bravura.py` | Enregistre la fonte Bravura auprès de ReportLab et fournit les glyphes SMuFL |
| `main.py` | CLI : orchestre parsing → rendu → écriture du PDF |
| `publish_github.py` | Crée le dépôt GitHub, commit et push automatiquement |

---

## ✅ Tests

La suite de tests couvre le parsing ABC, la configuration et le rendu PDF
(y compris la vérification **pixel par pixel** que les 8 couleurs sont bien
rendues) :

```bash
python -m pytest tests/ -v
```

Résultat attendu :

```
26 passed
```

---

## 📜 Licences & crédits

- **Code du projet :** MIT.
- **Fonte Bravura** (`assets/`) : © Steinberg Media Technologies GmbH,
  distribuée sous **SIL Open Font License 1.1** — voir
  <https://github.com/steinbergmedia/bravura>.
- Standard **SMuFL** : <https://w3c.github.io/smufl/>.
- **ABC notation** : <https://abcnotation.com>.

---

<p align="center">Fait avec ❤️ pour rendre la musique accessible aux plus petits.</p>