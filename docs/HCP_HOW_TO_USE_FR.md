# Healthcare Presentation Assistant (HPA)

## Guide utilisateur pour professionnels de santé

## Objectif

Healthcare Presentation Assistant (HPA) aide les professionnels de santé à
préparer des présentations PowerPoint scientifiques à partir de PDF qu’ils
fournissent.

HPA aide à la rédaction, à la revue et à l’export. Il ne remplace pas le
jugement professionnel, la revue scientifique, les politiques institutionnelles
ou la décision clinique.

## Avant de commencer

Utilisez uniquement des PDF que vous êtes autorisé à utiliser et qui sont
pertinents pour votre présentation. Ne téléversez aucune donnée patient
identifiable. Utilisez Patient Case Mode uniquement avec un cas entièrement
désidentifié ou fictif.

## 1. Créer un compte et un profil

1. Ouvrez le lien HPA.
2. Créez un compte avec un identifiant et un mot de passe.
3. Sélectionnez votre rôle professionnel.
4. Sélectionnez anglais, français ou arabe.
5. Connectez-vous.

Votre profil aide HPA à adapter son style de communication. Il ne remplace pas
votre responsabilité professionnelle ni les clarifications de périmètre si elles
sont demandées.

## 2. Créer un Project

Créez un Project pour chaque présentation indépendante.

Chaque Project dispose de sa propre bibliothèque de PDF, Resource Overview,
Resource Chat, conversation de présentation, blueprint, Agenda, slides,
export PowerPoint et historique d’audit.

Exemple :

```text
Mise à jour sur la dépression — réunion avec les médecins généralistes
```

## 3. Choisir le mode de preuves

| Mode | Objectif |
|---|---|
| BM25 retrieval | Mode par défaut. HPA sélectionne les passages PDF les plus pertinents pour la question ou la génération. |
| Direct bounded PDF context | Mode expérimental. HPA utilise une portion équilibrée et limitée des mêmes PDF, sans classement BM25. |

Pour comparer les deux modes correctement, utilisez les mêmes PDF, la même
question et les mêmes conditions de présentation.

## 4. Optionnel : Patient Case Mode

Utilisez ce mode uniquement avec des informations entièrement désidentifiées.
HPA tente de bloquer les adresses e-mail, numéros de téléphone, identifiants de
dossier médical, numéros de sécurité sociale, adresses postales et dates
complètes présentes dans un texte de cas patient.

Une date de publication dans un PDF scientifique ne bloque pas à elle seule une
guideline ou un article normal. Patient Case Mode est un garde-fou, pas une
certification HIPAA ou une garantie formelle de désidentification.

## 5. Utiliser l’espace Resources

L’espace Resources est séparé du Presentation assistant. Utilisez-le pour
explorer les PDF avant de produire les slides.

### Ajouter des PDF

1. Ouvrez **Resources**.
2. Importez un ou plusieurs PDF lisibles.
3. Attendez l’extraction du texte.
4. Vérifiez le titre, la source et le nombre de pages affichés.

### Resource Overview

Utilisez **Generate Resource Overview** pour obtenir une synthèse concise des
PDF importés. Elle peut aider à identifier l’idée générale, les thèmes
principaux, les accords ou divergences, les limites et des angles possibles de
présentation.

Utilisez cette fonction comme point de départ à la discussion, pas comme une
conclusion scientifique finale.

### Resource Chat

Utilisez **Resource Chat** pour poser des questions sur les PDF importés.

```text
Que dit la guideline sur le traitement de première ligne ?

Quelles sont les limites de ces ressources ?

Les deux documents sont-ils cohérents sur le suivi ?
```

Si les ressources sont insuffisantes, HPA doit demander un PDF plus pertinent
ou une clarification plutôt que d’inventer une réponse.

> **Note :** Resource Overview et Resource Chat sont des fonctionnalités
> d’exploration. Les citations des slides générées par IA subissent une
> validation système plus stricte avant validation et export PowerPoint.

### Gérer les ressources

Vous pouvez ajouter ou supprimer un PDF, le rattacher à la présentation ou le
détacher. Seuls les PDF explicitement rattachés et validés par l’utilisateur
peuvent servir de preuve pour le blueprint et les slides.

## 6. Démarrer le workflow de présentation

Ouvrez **Presentation assistant** et décrivez votre objectif.

```text
Je souhaite une présentation éducative de 15 minutes en français pour des
médecins généralistes sur la prise en charge de la dépression, basée sur la
guideline importée.
```

HPA peut demander le sujet, le public cible, le type de présentation, la durée,
la langue, l’objectif pédagogique ou une clarification de périmètre
professionnel.

Si une clarification est demandée, répondez par une phrase claire sur votre rôle
et votre objectif.

```text
Je suis délégué médical de formation vétérinaire et je prépare une information
scientifique destinée aux professionnels de santé humaine.
```

## 7. Valider les ressources de présentation

Avant de générer le blueprint :

1. Sélectionnez les PDF pertinents.
2. Vérifiez la sélection.
3. Cliquez sur **Validate resources and continue**.

Cette étape est une validation humaine. HPA ne peut pas valider les ressources
à votre place.

## 8. Ajouter les détails de la première slide

Vous pouvez ajouter :

- le nom du présentateur ;
- le titre professionnel ;
- l’organisation ;
- le nom de l’événement ;
- le lieu ;
- la date de présentation.

Ces éléments sont fournis par l’utilisateur ; HPA ne les invente pas.

## 9. Revoir le Blueprint et l’Agenda

Après validation des ressources, demandez à HPA de générer le blueprint. Il
propose la structure de la présentation, les titres de slides, les objectifs
pédagogiques, les messages clés et la progression narrative.

L’Agenda est revu séparément et devient la slide 2 du PowerPoint exporté.

Pour chaque élément du blueprint, vous pouvez approuver, refuser et commenter,
modifier directement, régénérer ou rédiger vous-même.

## 10. Générer et revoir les slides

Après approbation du Blueprint et de l’Agenda, générez les slides.

Pour chaque slide, vous pouvez approuver, refuser et commenter, régénérer avec
votre retour, modifier directement, la marquer comme modifiée par l’utilisateur
ou la rédiger vous-même.

### Slides générées par IA

Les slides IA doivent être soutenues par les PDF sélectionnés et validés. HPA
vérifie que :

1. le PDF cité fait partie de la sélection ;
2. la page citée existe ;
3. l’extrait cité est réellement présent sur cette page.

Si les preuves sont insuffisantes pour une slide, HPA suspend cette slide plutôt
que d’inventer du contenu. Vous pouvez ajouter un PDF plus pertinent, modifier
le blueprint ou rédiger la slide vous-même.

### Contenu utilisateur

Les slides et éléments de blueprint sont étiquetés comme générés par IA,
modifiés par l’utilisateur ou rédigés par l’utilisateur. Une slide rédigée par
l’utilisateur est créée à partir de son contenu sans appel de génération IA.

## 11. Validation finale et export PowerPoint

Lorsque toutes les slides sont revues :

1. Approuvez la présentation finale.
2. Exportez le PowerPoint.

L’export contient la slide de titre, l’Agenda en slide 2, les slides revues et
une slide finale **Resources and validation**.

## 12. Scénarios de test suggérés

Merci de tester :

1. L’import de PDF pertinents.
2. Resource Overview.
3. Une question clairement répondue dans le PDF.
4. Une question non répondue par le PDF.
5. La validation des ressources.
6. La revue du Blueprint et de l’Agenda.
7. La génération des slides.
8. Une citation et sa page PDF.
9. La modification ou rédaction manuelle d’une slide.
10. L’export PowerPoint.
11. La comparaison BM25 et Direct bounded PDF context, si possible.

## 13. Retour d’expérience

Merci de compléter le formulaire d’évaluation HCP fourni avec HPA.

Les retours utiles concernent notamment :

- la clarté du workflow ;
- la compréhension des citations ;
- les refus de réponses non soutenues ;
- le gain de temps apporté par le Blueprint ;
- la facilité de modification et de validation ;
- la qualité du PowerPoint ;
- votre préférence entre BM25 et Direct bounded PDF context.

Merci de contribuer à l’évaluation de HPA.
