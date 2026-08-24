# HPA — Journal d’évolution de l’architecture et de la réflexion

**Auteur : Anis Boubala**

## But de ce document

Ce document conserve mon cheminement vers l’architecture actuelle de
Healthcare Presentation Assistant (HPA). Il ne décrit pas seulement le résultat
final : j’y garde mes hypothèses initiales, les difficultés rencontrées, les
solutions essayées et les questions qui restent ouvertes.

L’objectif est qu’un senior en Applied GenAI, software architecture ou produit
de santé puisse comprendre ma démarche, identifier les erreurs de méthode et
m’orienter sur les prochaines améliorations. Les commentaires externes peuvent
être ajoutés à la fin de chaque section ou dans un document de review daté.

Les architectures remplacées sont conservées dans
[architecture-history](architecture-history/). L’architecture actuellement en
vigueur est définie dans [ADR-0007](../ADR.md).

## Point de départ

Le projet est né d’une question métier : comment aider un professionnel de
santé à préparer une présentation scientifique à partir de ses propres PDF,
sans laisser un modèle inventer des références, des recommandations ou une
certitude qu’il ne possède pas ?

Mon intuition initiale était que le prompt engineering seul ne suffisait pas.
Je voulais reproduire une partie du processus réel : choix des sources,
préparation d’un plan, relecture, validation des slides et export final. Cette
intuition est restée constante ; la manière de l’implémenter a beaucoup évolué.

## Étape 1 — Un agent conversationnel pour piloter le parcours

### Hypothèse initiale

J’ai commencé par un agent LangGraph avec un état, un prompt système, un
harness, une boucle d’outils et des use cases. L’idée était que l’agent puisse
collecter le contexte, créer une présentation, générer un blueprint puis des
slides tout en demandant des validations humaines.

### Ce qui a bien fonctionné

- Le projet n’était pas un simple appel LLM : il avait déjà un état et des
  règles métier.
- La séparation prompt / graph / outils / use cases m’a permis d’identifier
  les responsabilités du système.
- Les validations humaines étaient présentes dès le début.

### Difficultés rencontrées

- Le chat pouvait devenir le point d’entrée de trop nombreuses actions métier.
- L’agent répétait parfois une demande de validation ou de clarification.
- Une phrase utilisateur ambiguë pouvait être interprétée comme une demande de
  génération alors que le système attendait une autre étape.
- Quand le workflow bloquait, l’utilisateur ne savait pas toujours où ni
  comment reprendre.

### Solution essayée

J’ai progressivement ajouté des contrôles de transitions, des messages de
blocage, des validations manuelles et un état plus détaillé. Cela a amélioré le
comportement, mais n’a pas supprimé la cause structurelle : le modèle restait
trop proche des commandes qui modifient l’état métier.

### Apprentissage

Un graphe et de bons prompts ne suffisent pas si le modèle garde une autorité
implicite sur le cycle de vie du produit. Les commandes qui modifient un projet
doivent être définies par le système et non déduites de la conversation.

## Étape 2 — Construire une frontière de preuve autour des PDF utilisateurs

### Problème identifié

Un assistant de présentation en santé ne peut pas utiliser ses connaissances
générales comme si elles étaient des sources. Les ressources doivent être
fournies par l’utilisateur et seules les ressources pertinentes doivent servir
de base aux affirmations scientifiques.

### Solution mise en place

- bibliothèque PDF par utilisateur et par Project ;
- extraction du texte par page ;
- découpage en chunks persistés dans SQLite ;
- sélection locale de passages avec BM25 ou contexte PDF borné ;
- conservation de `resource_id`, page et extrait ;
- validation système des citations des slides IA.

### Difficultés rencontrées

- Envoyer des PDF entiers au modèle était lent, coûteux et peu contrôlable.
- Les sources pouvaient être utilisées pour discuter sans être prêtes pour la
  production d’une présentation.
- Une citation générée par le modèle n’était pas automatiquement une preuve.
- BM25 fonctionne par recouvrement lexical et peut manquer des formulations
  sémantiquement proches.

### Solution essayée

J’ai séparé la bibliothèque de ressources, l’analyse des ressources et les
ressources explicitement attachées puis validées pour une présentation. Le
système vérifie désormais qu’une citation de slide pointe vers une ressource
sélectionnée, une page existante et un extrait réellement présent.

### Question ouverte pour un senior

La stratégie BM25 est volontairement simple, locale et explicable. Est-ce une
base d’évaluation suffisante pour un premier pilote HCP ? Quel protocole et
quels seuils permettraient de décider rationnellement si une couche de
recherche sémantique est nécessaire ?

## Étape 3 — Séparer exploration des ressources et production

### Problème identifié

L’utilisateur peut vouloir téléverser un PDF, le résumer ou en discuter sans
vouloir produire une présentation. Mélanger cela avec la validation de preuves
pour la génération créait une confusion : l’outil pouvait demander une
validation alors que l’utilisateur souhaitait seulement lire ou questionner un
document.

### Solution mise en place

Le produit distingue désormais trois espaces :

1. **Resources** : import, sélection pour la présentation et validation ;
2. **Resource Analysis** : résumé et discussion uniquement à partir des PDF ;
3. **Presentation Studio** : création, génération, revue et export.

Les historiques de conversation Resource Analysis et Presentation Studio sont
séparés afin de ne pas mélanger une discussion documentaire et un échange sur
la présentation.

### Apprentissage

Une même source de données peut servir plusieurs intentions métier. Les
séparer dans l’interface et dans le state réduit les ambiguïtés et rend les
règles plus simples à tester.

## Étape 4 — Faire du système, et non du chat, l’autorité du workflow

### Problème identifié

La conversation restait fragile pour déclencher des opérations importantes.
Les bugs observés autour de la validation, de la génération et de la reprise
après erreur ont montré qu’un utilisateur ne doit pas avoir à trouver la bonne
formulation pour faire avancer un workflow.

### Solution mise en place

- création de présentation par formulaire contrôlé ;
- boutons explicites pour générer blueprint et slides ;
- jobs API asynchrones pour les opérations longues ;
- relecture serveur de l’état, des ressources validées et du périmètre
  professionnel avant tout appel au modèle ;
- verrou d’un job d’écriture par Project ;
- erreurs métier structurées avec code, étape et action de reprise ;
- test end-to-end sans fournisseur LLM réel.

Le principe actuel est :

```text
Le système vérifie les règles et les preuves
→ l’utilisateur déclenche une commande explicite
→ le modèle génère dans un contexte borné
→ le système valide ce qui est vérifiable
→ l’utilisateur approuve le livrable
```

### Ce que je pense avoir compris

Le modèle apporte l’interprétation du langage et la génération. Le système
autour du modèle apporte les règles métier, les états, les contrôles, la
mémoire, les limites de contexte, les preuves, les erreurs et l’audit. Le
prompt, le context engineering, le harness, les loops et le graph engineering
sont utiles pour orienter le modèle dans cet environnement ; ils ne remplacent
pas le code qui impose les règles.

## Difficultés transversales rencontrées

| Difficulté | Risque produit | Réponse apportée |
|---|---|---|
| Historique chat perdu après erreur fournisseur | perte de contexte utilisateur | persistance du tour utilisateur avant l’appel LLM |
| Projet figé après une slide sans preuve | parcours impossible à reprendre | état de résolution ciblé par slide : PDF, réécriture ou contenu utilisateur |
| Informations de titre répétées | expérience frustrante | préremplissage du formulaire depuis le contexte déjà collecté par chat |
| Interface qui bloque pendant un appel LLM | perte de confiance et mauvaise UX | jobs API et polling côté `/app` ; actions explicites dans Streamlit |
| Provenance peu lisible | utilisateur ne comprend pas les références | affichage du titre PDF, détails techniques accessibles à la demande |
| Écritures concurrentes | écrasement d’état Project | verrou de job d’écriture unique par Project |

## Première expérimentation utilisateur — nouveaux écarts observés

Lors d’un premier test du parcours complet, j’ai observé que les règles et les
tests ne suffisent pas à eux seuls à garantir une expérience fluide. Avec le
même ensemble de PDF fourni par l’utilisateur, le mode BM25 a permis de
générer un blueprint puis a bloqué la génération des slides pour manque de
preuve. Le mode de contexte PDF direct borné a, lui, poursuivi le parcours.

Je ne considère pas cela comme une raison d’assouplir la règle de preuve ou de
faire inventer le modèle. Je dois d’abord comprendre si une slide donnée n’est
réellement pas soutenue par les PDF, ou si BM25 ne retrouve pas un passage
pourtant pertinent. La différence entre une requête large de blueprint et une
requête précise de slide rend cette investigation nécessaire. Le prochain pas
est de tracer les requêtes, chunks, scores, pages, seuils et raisons de refus
pour les deux modes sur un même cas reproductible.

En relisant l’implémentation, j’ai identifié un écart plus précis : BM25
évaluait le meilleur chunk individuel, alors que le mode Direct agrégeait les
termes retrouvés dans plusieurs chunks de sa fenêtre. Le test ne comparait donc
pas seulement deux méthodes de récupération, mais aussi deux calculs de
suffisance de preuve.

J’ai corrigé ce point en séparant clairement deux décisions : chaque mode
sélectionne ses passages, puis le système applique la même règle aux passages
sélectionnés. Un seul passage doit contenir le niveau minimal de support requis
pour la requête. Il n’est plus possible de faire passer une génération en
additionnant des termes trouvés dans plusieurs pages. Le diagnostic conserve le
mode, les pages sélectionnées, le seuil et, pour BM25, les scores. Cela ne rend
pas BM25 sémantique ; cela rend la comparaison et le refus traçables.

Le test a aussi montré deux sujets produit : l’utilisateur ne trouvait pas assez
clairement comment passer de Resources à Presentation Studio après validation,
et Resource Chat ne donnait pas une impression de conversation continue pendant
le travail du modèle. J’ai conservé les commandes de production dans une
interface métier déterministe, mais Resources affiche maintenant l’action
autorisée par le serveur pour générer le blueprint et un accès clair à
Presentation Studio. Pour Resource Chat, la question est affichée immédiatement
dans son panneau avec un état de traitement, sans figer toute l’interface.

Enfin, le test a formulé un besoin que je n’avais pas suffisamment distingué de
la génération textuelle : placer un tableau précis d’un PDF sur une slide
précise. Mon hypothèse est qu’il faut d’abord une sélection déterministe de la
ressource, page et zone du tableau, avec conservation de la preuve, plutôt que
demander au LLM de reconstruire des chiffres. J’aimerais qu’un senior me dise
si cette frontière entre insertion sourcée et génération est la bonne approche.

## Ce que j’aurais probablement dû faire plus tôt

Avec le recul, j’aurais commencé par écrire avant le code :

1. les états métier ;
2. les commandes autorisées dans chaque état ;
3. les erreurs et chemins de reprise ;
4. un scénario end-to-end HCP ;
5. les critères d’acceptation et les preuves à conserver.

Je suis passé par une approche plus exploratoire, avec beaucoup d’itérations
sur le chat et l’interface. Cette démarche m’a permis de découvrir les vrais
problèmes métier, mais elle a aussi créé des corrections successives. Je veux
savoir si cette séquence reste saine pour un projet d’apprentissage et comment
la rendre plus disciplinée pour les prochains projets.

## Questions de méthodologie à discuter avec un senior

1. À quel moment faut-il figer un modèle d’état avant de continuer à enrichir
   les fonctionnalités ?
2. Comment distinguer une règle qui doit être dans le prompt, dans le graph ou
   dans un service métier déterministe ?
3. Quelles parties de cette architecture sont suffisamment robustes pour un
   pilote HCP, et lesquelles sont encore seulement des choix de MVP ?
4. Quel est le meilleur prochain investissement : évaluation RAG, tests
   navigateur, workers durables, ou simplification du domaine ?
5. Quels indicateurs permettront de dire que le système améliore réellement le
   travail du HCP sans dégrader la fidélité aux sources ?

## Espace de feedback externe

| Sujet | Observation du reviewer | Correction proposée | Priorité |
|---|---|---|---|
| Méthodologie de conception |  |  |  |
| États et règles métier |  |  |  |
| RAG et provenance |  |  |  |
| Tests et évaluation HCP |  |  |  |
| Prochaine étape technique |  |  |  |

## Références internes

- [ADR-0007](../ADR.md) : architecture actuelle et décisions actives ;
- [architecture-history](architecture-history/) : traces synthétiques des
  architectures précédentes ;
- [FANIS_REVIEW.md](FANIS_REVIEW.md) : demande de review en anglais ;
- [EVALUATION.md](EVALUATION.md) : stratégie d’évaluation système ;
- [HCP_EVALUATION.md](HCP_EVALUATION.md) : formulaire de retour HCP.
