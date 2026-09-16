# Reusable implementation prompt

Copy the French prompt into a fresh conversation in this repository. Replace the phase path and slice ID for subsequent work.

```text
Je t’autorise à exécuter uniquement la sous-étape 00.1 de
`docs/phases/00-baseline.md`.

Lis les consignes AGENTS.md applicables, `docs/phases/README.md`, le fichier
de cette phase et son état de reprise, puis les sections du PRD et les fichiers
de code nécessaires. Le PRD fait autorité. Ne charge pas toutes les phases.

Vérifie l’état Git et les prérequis. Préserve mes modifications. Repère ce qui
existe déjà, explique brièvement les actions prévues, puis exécute cette
sous-étape jusqu’à ses critères d’acceptation, sans redemander confirmation
pour les actions courantes déjà autorisées. Si elle est trop vaste, découpe-la
en unités vérifiables avant de commencer. Pose une question seulement si une
décision produit indispensable ne peut pas être déduite.

Conserve l’architecture et les contrôles déterministes. Travaille sur /app,
avec des données publiques ou synthétiques, dans le périmètre de la phase.
Documente en anglais et explique-moi en français.

Lance les vérifications adaptées et examine le diff. Distingue les résultats
réussis, échoués, ignorés et non vérifiés. Mets à jour l’état de reprise avec
les changements, décisions, preuves et la prochaine sous-étape exacte.
Ne marque aucune validation humaine comme obtenue sans mon accord explicite.

Termine par : résultat concret, fichiers modifiés, vérifications, points
restants et une courte explication pédagogique. Arrête-toi à la limite de
cette sous-étape ; ne commence pas automatiquement la suivante.
```

Phase 00 is an audit: do not change application behaviour. For later sessions,
use the next exact slice from the handoff. Review and explicitly approve a
completed phase gate before starting the next phase. Record decisions and
blockers in the file rather than relying on previous chat memory.
