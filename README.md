# businessmachine-work

Code retieval.

## Idea

**project structure**

Say you have a project called `alpha`. You also have a git submodule `alpha-work`.

`alpha-work` is a normal git project. Add or change code and version control.

`alpha`, on the other hand, simply commit's along with every change to `alpha-work` a chat prompt that created the change to `alpha-work`.

**indexing of project data**

You embed and index all `alpha` commit messages against the effected files.

`alpha embeddings`
```
   {
     <commit-message-embedding>: [<files>, ..]
     <commit-message-embedding>: [<files>, ..]
     <commit-message-embedding>: [<files>, ..]
   }
```

**file retrieval**

Embed the prompt, and find related files based on matching `alpha embeddings`.

**answer prompt**

Structure prompt something like this.

```
{pre-prompt}\n{prompt}\n{post-prompt}\n(files}
```
## file structure

The aim.
```
project/
  .git/
  .businesmachine/
    .git
```

I'm not quite sure how to do that just yet, as we'd need to unest the submodule.

Simplified for ease for ease for now.

```
project/
  .git/
  project-work/
    .git/
```

### project-work

Your git project.

### .businessmachine

A monorepo that has project and .businessmachine/project as a submodules.

