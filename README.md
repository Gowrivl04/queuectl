# QueueCtl - Your Friendly Task Manager 

Hi there! Welcome to QueueCtl, a simple yet powerful way to manage your background tasks. Think of it as your personal assistant that handles jobs in order of importance, gives tasks another try if they fail, and keeps you updated on what's happening.

## What Can It Do? 

QueueCtl makes your life easier by:
- Managing your tasks (we call them jobs) in an organized way
  Letting important jobs skip the line (priority system)
- Automatically retrying tasks that fail
   Showing you what's happening in real-time
-  Working smoothly on both Windows and Mac/Linux
   Looking good in your terminal with colors and clear information

## Getting Started in 5 Minutes 

1. First, set up your workspace (one-time setup):
```powershell
# Tell QueueCtl where to store your tasks
$env:QUEUECTL_LIBSQL_DSN="file:local.db"
```

2. Start your dashboard to see what's happening:
```powershell
queuectl dashboard  # Then open http://localhost:8080 in your browser
```

3. Start a worker (this is like hiring an assistant):
```powershell
queuectl worker
```

4. Add some tasks to try it out:
```powershell
# A simple task
queuectl enqueue "echo 'My first task!'"

# An important task that goes to the front of the line
queuectl enqueue --priority 10 "echo 'Urgent task!'"

# A task that can try up to 5 times if it fails
queuectl enqueue --retries 5 "echo 'Keep trying!'"
```

## Watching Your Tasks 👀

Visit your dashboard at http://localhost:8080 to see:
-  How many tasks are waiting, running, or finished
   Which workers are active
-  How tasks are performing over time
   Detailed information about each task

### Available Dashboard Pages
- `/api/jobs` - See how your tasks are doing
- `/api/workers` - Check on your workers
- `/api/history` - Look back at what's been done

## Command Guide 

### Adding Tasks
```powershell
# Basic task
queuectl enqueue "your_command"

# Important task
queuectl enqueue --priority 10 "important_task"

# Task that can retry if it fails
queuectl enqueue --retries 5 "tricky_task"
```

### Checking on Tasks
```powershell
# See details about a specific task
queuectl show <task_id>

# Test the system with multiple tasks
queuectl stress -n 10 -d 100  # Creates 10 test tasks

## Task States �

Your tasks can be in one of these states:
1. `pending` - Waiting patiently to be worked on
2.  `processing` - Currently being worked on
3.  `completed` - Successfully finished
4.  `failed` - Something went wrong, but we'll try again
5.  `dead` - Failed too many times and won't be retried

## Making It Your Own 

You can customize QueueCtl by setting these environment variables:
- `QUEUECTL_LIBSQL_DSN`: Where to store your tasks
- `QUEUECTL_MAX_RETRIES`: How many times to retry failed tasks
- `QUEUECTL_DASHBOARD_PORT`: Which port to use for the dashboard

## For Developers 

Here's what's under the hood:
-  Async job processing for speed
-  SQLite-based storage that won't lose your data
-  Priority system so important tasks run first
-  Automatic retry when things go wrong
-  Real-time statistics
- Works on Windows, Mac, and Linux

## Want to Help? 

Feel free to:
-  Report any bugs you find
-  Suggest new features
-  Help improve the code

## Quick Demo Script 

Here's a quick demo script to show it off:

1. Open three terminal windows
2. In terminal 1:
   ```powershell
   $env:QUEUECTL_LIBSQL_DSN="file:local.db"
   queuectl dashboard
   ```

3. In terminal 2:
   ```powershell
   $env:QUEUECTL_LIBSQL_DSN="file:local.db"
   queuectl worker
   ```

4. In terminal 3:
   ```powershell
   $env:QUEUECTL_LIBSQL_DSN="file:local.db"
   # Create some test jobs
   queuectl stress -n 5 -d 100
   # Add a high-priority job
   queuectl enqueue --priority 10 "echo 'VIP task!'"
   ```



## License


MIT - Feel free to use and modify as you like! 📄
