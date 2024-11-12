# Journal

## Progress journal, 2024-11-11

### Done today

- Restructured the directories to make user folders at the top of the hierarchy.
- Added a new user

### Problems

- I'm not sure how to handle the user's data apart from the current JSON files. I'm thinking of using a database, but I'm not sure how to set it up.
- I've restructed the directories, but I'm not sure if this is the best way to do it or whether I have found all the places where I need to change the paths.

### To do

- Move user data to user folders.
- Set up a database for the user data.
- Create a new user class to handle the user data.
- Create a new branch
  - Add ability to force build LaTeX files.
  - Remove the connection to the Overleaf API.

## Progress journal, 2024-11-12

### Done today

- Added ability to generate a podcast script from the final PDF.
- Added ability to generate podcast audio from the podcast script.
- Added configurable settings for generating the podcast audio.
  - The setting is a simple boolean for now, but I may expand it later.
- Merged all branches back to main, after pushing main to the remote repository (idk what happened that it wasn't already there).

### Problems

- Realised the "main" branch was not pushed to the remote repository, so I had to push it.
- The generated podcasts are kinda lackluster, so I want to look at extra sound effects or something.
- The podcasts aren't great to listen to, let alone come back to.
  - Each section is far too short. 11 sections in 8 minutes means no real discussion is possible.
  - I want to look at generating the script for each section individually, while referring to the section before and after to ensure continuity.
  - I can then stitch the sections together to create a longer podcast, possibly with some music or sound effects in between.

### To do

- Create new user creation class.
- Find out if the PDF reading can be parallised.
- Parallelise the summary generation.
- Parallelise the podcast generation, once it is split into sections.
- Update the app_planning.md file with a scope for the podcasts.
- Create a new branch for the podcast improvements.
