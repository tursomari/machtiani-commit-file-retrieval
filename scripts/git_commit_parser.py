import subprocess
import json

def get_commit_info(commit_ref):
    try:
        # Get the commit OID and message
        commit_oid_message = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%H%n%B", commit_ref],
            capture_output=True, text=True, check=True
        )

        # Get the list of files changed in the commit
        commit_files = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_ref],
            capture_output=True, text=True, check=True
        )

        # Separate the OID and message
        output = commit_oid_message.stdout.strip().split("\n")
        oid = output[0]
        message = "\n".join(output[1:])

        # Get the list of changed files
        files = commit_files.stdout.strip().split("\n") if commit_files.stdout.strip() else []

        return {
            "oid": oid,
            "message": message,
            "files": files
        }
    except subprocess.CalledProcessError as e:
        print(f"Error processing commit {commit_ref}: {e}")
        return None

def iterate_commits(limit=10):
    commits = []
    for i in range(limit):
        commit_ref = f"HEAD~{i}"
        commit_info = get_commit_info(commit_ref)
        if commit_info:
            commits.append(commit_info)
        else:
            break  # Stop if we've reached the end of the commit history or encountered an error
    
    return commits

if __name__ == "__main__":
    limit = 1000  # Number of commits to retrieve
    commit_logs = iterate_commits(limit)

    print(json.dumps(commit_logs, indent=2))

