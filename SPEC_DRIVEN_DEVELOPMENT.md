# Spec Driven Development

## Step 0: Create feature spec folder

Create a new folder in `/.specs/001-like-posts`

## Step 1: Write your requirements.md

Write a `requirements.md` in your new folder. Here is the template.

```markdown
# Feature: Like a Post

## Problem
Users want to be able to like posts so they can see which posts are popular.

## User Stories
- As a user, I want to ...

## Out of Scope
- Post searching by like count

## Constraints
- Use the existing Post schema
```

## Step 2: Generate your design.md

```plaintext
Read /.specs/001-like-posts/requirements.md. Draft a design.md in the same folder. It outlines the overall architecture and design for this feature.
```

## Step 3: Generate your tasks.md

```plaintext
Read /.specs/001-like-posts/design.md. Draft a tasks.md in the same folder. It outlines the step-by-step tasks (as checkboxes) to implement which the agent will mark each one when finished.
```

## Step 4: Generate your tests.md

```plaintext
Read /.specs/001-like-posts/tasks.md. Draft a tests.md in the same folder. It outlines all the happy path and edge case tests that need to be implemented.
```

## Step 5: Have your Agent code the feature to spec

```plaintext
Read /.specs/001-like-posts/*.md. Follow the task checklist in tasks.md. Update the checkboxes as you complete each item. Run the tests before marking complete.
```
