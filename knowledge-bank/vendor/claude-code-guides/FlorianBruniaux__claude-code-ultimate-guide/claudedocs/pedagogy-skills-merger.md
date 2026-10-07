# Pedagogy Note: Skills–Commands Merger (CC 2.1.3)

Version du changement : Claude Code 2.1.3, released 2026-01-11
Applicable à tout contenu publié après cette date.

---

## 1. Ce qui a changé

**Avant 2.1.3** : deux mécanismes distincts.
- `.claude/commands/` — templates Markdown invoqués via `/nom-command` par l'utilisateur
- `.claude/skills/` — modules de connaissance chargés par le modèle selon le contexte

**Depuis 2.1.3** : un seul mécanisme.
- `.claude/skills/` — tout. Les skills ont deux modes d'invocation :
  1. **User-invocable** : l'utilisateur tape `/nom-skill` (exact comportement des anciennes commands)
  2. **Model-invocable** : le modèle charge la skill automatiquement si la description correspond au contexte
  3. **Les deux** : une skill peut être déclenchée des deux façons (par défaut, sans frontmatter spécial)

Pour restreindre une skill à l'invocation utilisateur uniquement (équivalent d'une ancienne command), ajouter dans le frontmatter :
```yaml
disable-model-invocation: true
```

Le répertoire `.claude/commands/` est déprécié. Les fichiers existants fonctionnent encore (rétrocompatibilité), mais tout nouveau développement doit aller dans `.claude/skills/`.

---

## 2. Comment expliquer la fusion au lecteur

**Ne pas dire** : "commands et skills ont fusionné" (trop technique, peu pédagogique).

**Dire** : "Les skills ont deux modes d'invocation. Quand un utilisateur tape `/nom`, c'est ce qu'on appelait autrefois une command. Quand le modèle charge la skill automatiquement selon le contexte, c'est l'ancien comportement skill. Les deux vivent maintenant dans `.claude/skills/` avec le même frontmatter YAML."

**Conserver le terme "slash command"** : il décrit comment l'utilisateur invoque une skill (via `/`), pas un type de mécanisme distinct. "Slash command" = skill avec invocation utilisateur. Le terme reste pertinent dans les tables de référence des built-in commands (`/clear`, `/compact`, etc.) et dans les explications d'usage.

**Ne pas supprimer "command"** de la terminologie built-in : `/clear`, `/compact`, `/help` restent des "built-in commands". La fusion ne touche que les mécanismes custom.

---

## 3. Nouveau tableau de comparaison Agent vs Skill

Le tableau Agent/Skill/Command (3 colonnes) devient Agent/Skill (2 colonnes) avec une note sur les modes d'invocation de Skill.

| Mécanisme | Déclenchement | Portée | Cas d'usage idéal |
|-----------|--------------|--------|-------------------|
| **Agent** | Task tool / invocation Claude | Session isolée | Audit one-shot, traitement parallèle |
| **Skill** | `/nom` (user) ou auto (modèle) | Partagé entre agents | Connaissance réutilisable, workflow codifié |

**Note d'invocation Skill** :
- User-invocable (`disable-model-invocation: true`) : `/tech:commit`, `/release-notes` — l'utilisateur déclenche manuellement
- Model-invocable : `security-guardian`, `tdd-node` — le modèle charge selon le contexte
- Les deux (défaut) : skills polyvalents, invocables des deux façons

**Règle de sélection rapide** :
- Tâche déléguée avec isolation de contexte → **Agent**
- Connaissance ou workflow à encapsuler → **Skill**
  - L'utilisateur déclenche → `disable-model-invocation: true`
  - Le modèle décide → laisser le défaut (model-invocable)
  - Les deux → laisser le défaut sans l'option

---

## 4. Exemples concrets par mode d'invocation

**User-invocable uniquement** (`disable-model-invocation: true`) :
- `/tech:commit` — l'utilisateur tape manuellement après avoir codé
- `/release-notes` — déclenché en fin de sprint par l'utilisateur
- `/ship` — séquence de deploy déclenchée intentionnellement

**Model-invocable uniquement** (sans frontmatter spécial, description précise) :
- `security-guardian` — chargé quand Claude détecte une auth ou une route sensible
- `tdd-node` — chargé quand Claude commence à écrire des tests
- `silence-framework-expert` — chargé sur les repos avec silence-ws

**Les deux** (défaut, description générale) :
- `pdf-generator` — l'utilisateur peut dire `/pdf-generator` ou Claude le charge sur "génère un PDF"
- `commit-craft` — déclenché par `/commit-craft` ou automatiquement avant un commit

---

## 5. Traitement éditorial par type de contenu

### Comparaison tables (3 mécanismes → 2)
Supprimer la ligne "Command" et ajouter une note sur les modes d'invocation de Skill.

### Exemples de structure de fichiers
```
.claude/
├── skills/       # Slash commands + knowledge modules (unified since CC 2.1.3)
├── agents/
├── hooks/
└── rules/
```
La ligne `commands/` est supprimée des diagrammes d'arborescence.

### Decision trees
Les branches "→ Command" deviennent "→ Skill (user-invocable)".

### Frontmatter examples
Tout exemple de `command` frontmatter dans `.claude/commands/` devient un exemple de skill dans `.claude/skills/` avec `disable-model-invocation: true` si l'ancien exemple était une command pure.

### Callout notes sur la fusion
Dans les whitepapers, remplacer le callout générique "convergence" par un callout factuel :
> **CC 2.1.3 (janvier 2026)** : `.claude/commands/` est désormais fusionné dans `.claude/skills/`. Pour créer l'équivalent d'une ancienne command, placez le fichier dans `.claude/skills/` et ajoutez `disable-model-invocation: true` au frontmatter YAML.

---

## 6. Ce qui ne change PAS

- La terminologie "slash command" pour les built-in commands (`/clear`, `/compact`, `/help`)
- Le concept "Skill Evals" (Capability Uplift vs Encoded Preference) — inchangé
- La structure interne d'un fichier skill (SKILL.md + ressources)
- Le frontmatter `allowed-tools`, `effort`, `name`, `description` — inchangés
- Les agents — inchangés
- Les hooks — inchangés
- Les règles — inchangées

---

## 7. Version et attribution

Changement documenté dans CC 2.1.3 release notes.
Source officielle : https://code.claude.com/docs/fr/skills
Applicable depuis : 2026-01-11
Guide version cible : 3.41.0 (minor bump — changement pédagogique majeur)