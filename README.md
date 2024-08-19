# businessmachine-work

Version control files and chats about the files.

## Idea

git add {businessmachine}
    git add {chat}

git add {submodule}
    git add {files}
    git commit {files} -m "{message}"

git commit -m "{prompt}"

embed prompt and map file(s).



prompt: How do I {x}?

---> embed {prompt} ---> {embedded prompt}

                        ---> find close matches to {embedded prompt} ---> {files}

                            ---> load {files}

                                ---> How do I do {x}?\n (files}

## businessmachine file structure

project/
  .businessmachine/
    project/
      {chat files}
    .git
  .git

## simplified businessmachine file strucutre

project/
  .businessmachine/
    .git
  project-work/
    .git


### project-work

Your git project.

### .businessmachine

A monorepo that has project and .businessmachine/project as a submodules.

