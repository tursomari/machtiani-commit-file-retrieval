import git
import json

def get_commit_info_at_depth(repo, depth):
    try:
        # Get the commit object at the given depth
        commit = repo.commit(f'HEAD~{depth}')

        # Get the commit message
        message = commit.message.strip()

        # Get the list of files changed in the commit
        files = []
        for diff in commit.diff(commit.parents[0] if commit.parents else None):
            files.append(diff.a_path)

        return {
            "oid": commit.hexsha,
            "message": message,
            "files": files
        }

    except Exception as e:
        print(f"Error processing commit at depth {depth}: {e}")
        return None

def get_commits_up_to_depth(repo_path, max_depth):
    try:
        repo = git.Repo(repo_path)
        commits = []
        for i in range(max_depth):
            commit_info = get_commit_info_at_depth(repo, i)
            if commit_info:
                commits.append(commit_info)
            else:
                break  # Stop if we've reached an invalid commit or error occurs

        return commits

    except Exception as e:
        print(f"Error accessing the repository: {e}")
        return []

if __name__ == "__main__":
    repo_path = '.'  # Path to your git repository
    depth = 10  # Depth or level of commits to retrieve
    commit_logs = get_commits_up_to_depth(repo_path, depth)

    print(json.dumps(commit_logs, indent=2))

