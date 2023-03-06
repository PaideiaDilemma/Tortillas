<div align = center>

# :flatbread: Tortillas - _A test runner for [IAIK/sweb](https://github.com/IAIK/sweb)_ :flatbread:

![Demo](https://github.com/PaideiaDilemma/Tortillas/actions/workflows/demo_ci.yml/badge.svg)
![Internal tests](https://github.com/PaideiaDilemma/Tortillas/actions/workflows/internal_tests_ci.yml/badge.svg)

</div>

This program might be useful for students doing the [operating systems course](https://www.iaik.tugraz.at/course/operating-systems) at TU Graz.

Tortillas is here to help with testing your sweb code. \
It takes your test cases and runs them in individual Qemu instances, while logging the output and monitoring for errors.

### Get started

- [Quickstart](#quickstart)
- [Manual setup](#manual-setup)

## Features

- Parallel test execution
- Test summary with errors from all test runs
- Configure how debug logs get parsed and interpreted
- Fancy progress bar
- Uses qemu snapshots to avoid booting multiple times
- Individual test configuration via test headers (timeout, expected exit codes)
- Detection of bootup, test completion and kernel panics

## Dependencies

- python >= 3.8
- pyyaml
- [enligthen](https://github.com/Rockhopper-Technologies/enlighten) _(Optional)_ for a progress bar

## Demo

![](.assets/demo.gif)

In this animation, Tortillas runs tests from the example. \
Note: After it ran, [grip](https://github.com/joeyespo/grip) was used to display tortillas_summary.md

### Example repo

The example submodule in this repository points to [tortillas-sweb](https://github.com/PaideiaDilemma/tortillas-sweb). \
Notable branches in this repo:

- `main` contains a minimal example
- `panic` demonstrates different test failures

### CI/CD

The [demo workflow](https://github.com/PaideiaDilemma/Tortillas/actions/workflows/demo_ci.yml?query=branch%3Amain) in this repository runs tortillas on the example repo.
_(Github requires you to be logged in to see the workflow output)_.

## Installation

```
git clone https://github.com/PaideiaDilemma/Tortillas
cd Tortillas
python -m pip install .\[fancy\] # Include progress bar dependency (recommended)
python -m pip install .          # No progress bar
```

## Quickstart

You can merge the main branch of the [example repo](https://github/PaideiaDilemma/tortillas-sweb) into your sweb.
Make sure you understand the changes this introduces.

```sh
# Currently at <path_to_your_sweb_repo>
git checkout -b tortillas-quickstart
git remote add tortillas-sweb https://github.com/PaideiaDilemma/tortillas-sweb
git fetch tortillas-sweb
git merge tortillas-sweb/main
tortillas # Should run mult.c with SUCCESS
```

## Manual setup

### Setup sweb

#### 1. Grub boot menu
You will need to set the grub boot timeout to 0, if you haven't already.

<details><summary>Example diff</summary>

```diff
diff --git a/utils/images/menu.lst b/utils/images/menu.lst
index cf7fd93d..25e6f493 100644
--- a/utils/images/menu.lst
+++ b/utils/images/menu.lst
@@ -1,5 +1,7 @@

 default 0
+timeout 0
+hiddenmenu

 title = Sweb
 root (hd0,0)
```

</details>

#### 2. Meta syscalls

Add two syscalls to your sweb and note their syscall numbers. \
One will signal bootup and the other one test completion. They don't need to do anything. You could name them `sc_tortillas_bootup` and `sc_tortillas_finished`.

Call those syscalls in `userspace/tests/shell.c:main`. \
The one for bootup should be called just before `while(running)` and the one for test completion inside the loop, after `handleCommand`.

<details><summary>Example diff</summary>

```diff
diff --git a/common/include/kernel/syscall-definitions.h b/common/include/kernel/syscall-definitions.h
index dd99d197..a3c6aadc 100644
--- a/common/include/kernel/syscall-definitions.h
+++ b/common/include/kernel/syscall-definitions.h
@@ -17,3 +17,5 @@
 #define sc_createprocess 191
 #define sc_trace 252

+#define sc_tortillas_bootup 1337
+#define sc_tortillas_finished 1338
diff --git a/common/source/kernel/Syscall.cpp b/common/source/kernel/Syscall.cpp
index 964cd5b4..e565a730 100644
--- a/common/source/kernel/Syscall.cpp
+++ b/common/source/kernel/Syscall.cpp
@@ -49,6 +49,10 @@ size_t Syscall::syscallException(size_t syscall_number, size_t arg1, size_t arg2
     case sc_pseudols:
       pseudols((const char*) arg1, (char*) arg2, arg3);
       break;
+    case sc_tortillas_bootup:
+      break;
+    case sc_tortillas_finished:
+      break;
     default:
       return_value = -1;
       kprintf("Syscall::syscallException: Unimplemented Syscall Number %zd\n", syscall_number);
diff --git a/userspace/tests/shell.c b/userspace/tests/shell.c
index a798ad27..88e27c0c 100644
--- a/userspace/tests/shell.c
+++ b/userspace/tests/shell.c
@@ -348,9 +348,11 @@ int main(int argc, char* argv[]) {
   printAvailableCommands();
   __syscall(sc_pseudols, (size_t)SHELL_EXECUTABLE_PREFIX,
             (size_t)dir_content, sizeof(dir_content), 0, 0);
+  __syscall(sc_tortillas_bootup, 0, 0, 0, 0, 0);
   while(running) {
     readCommand();
     handleCommand();
+    __syscall(sc_tortillas_finished, 0, 0, 0, 0, 0);
   }
   return exit_code;
 }
```

</details>

##### Why do I need to add syscalls to sweb?
In short, because it makes detection of bootup and test completion
easier and more reliable. For a better answer see [Interrupt/Syscall detection](#interruptsyscall-detection).

#### 3. Add `tortillas_config.yml`

Copy [`tortillas_config.yml`](tortillas_config.yml) from this repository to your sweb. Replace the numbers at `sc_tortillas_bootup` and `sc_tortillas_finished` with your syscall numbers.

See [Tortillas config](#tortillas-config)

### Adding test specifications

Tortillas requires all tests to have a header in yaml format.
For now, you can add this to the top of `userspace/tests/mult.c` (included in base-sweb).
```yaml
/*
--- # Test specification
category: base
description: |
    Multiplies two matrices containing pseudo random numbers
    and returns the sum of the resulting matrix.

expect_exit_codes: [1237619379]
*/
```
Verify the setup, by [running tortillas](#running-tortillas). \
`mult` should run and complete with SUCCESS.

You can now check out [Test specifications](#test-specifications) and add test specifications
to your tests.

### CI/CD _(Optional)_

If you want a CI/CD pipeline, you have the following possibilities:

#### 1. Set up a [gitlab runner](https://docs.gitlab.com/runner/)
This requires a publicly accessible server. If you have your own runner, you can add it to your repository.

You can use a workflow similar to [`gitlab-ci-example.yml`](gitlab-ci-example.yml)
This might be the best solution, but has the caveats of _you needing a server_ and _not being able to upload artifacts_ (I think it is disabled on IAIK gitlab).

#### 2. Set up a [repository mirror](https://docs.gitlab.com/ee/user/project/repository/mirror/)
It is possible to mirror your gitlab sweb repo to github,
where you can run a workflow with Github Actions, similar to [the one from tortillas-sweb](https://github.com/PaideiaDilemma/tortillas-sweb/blob/main/.github/workflows/sweb-ci.yml).
Make sure you use a __private repo__ though.

Of course, this way, your pipeline will not be visible within gitlab.

<sub><sup>If you have another way of running a CI/CD pipeline, add it here!</sup></sub>

## Cli Usage
See `tortillas --help`

Note: You do not necessarily have to install tortillas. You can also run it from the Tortillas source directory, like this:
```
python -m tortillas -S <path_to_your_sweb_repo>
```

#### Examples

###### Running tortillas

```sh
# If your are at <path_to_your_sweb_repo>
tortillas
# From any other directory:
tortillas -S <path_to_your_sweb_repo>
```

###### Run a test selection

Tortillas supports running tests selected by tag, category or glob pattern.
```
tortillas --tag pthread         # Run all tests tagged with 'pthread'
tortillas --category malloc,brk # Run all tests in the 'malloc' and 'brk' categories
tortillas --glob test*          # Run all tests, that match 'userspace/tests/test*.c'
```

## Tortillas config

The `tortillas-config.yml` file configures tortillas to fit your sweb.

Per default it is expected to be at `<path_to_your_sweb_repo>/tortillas-config.yml`.\
You can specify the config path with `tortillas -C <path_to_tortillas_config>`

### Configure log handling _(You might need this)_

You can define how logs of your sweb are handled.

Best understood by looking at an example.
```yaml
analyze:
  - name: lock_logs
    scope: 'LOCK'
    pattern: '(.*)'
    mode: add_as_error
  ...
```
__This does the following:__
- Every log from `debug(LOCK, ...)` that matches `(.*)` (which means everything) will be parsed into a container.
- All logs in that container will be added to error summaries (`add_as_error`).

#### Pattern

The `pattern` field must contain a regex pattern, that matches the desired string in __group 1__ (usually denoted by the first set of parenthesis).

#### Why you might need this

Base-sweb logs exit codes like this:
```c
debug(SYSCALL, "Syscall::EXIT: called, exit_code: %zd\n", exit_code);
```

Tortillas captures them with this config entry:
```yaml
# Exit codes
  - name: exit_codes # Unique identifier
    scope: SYSCALL # as in `debug(SYSCALL, ...)`
    pattern: 'Syscall::EXIT: called, exit_code: (\d+)' # match exit code
    mode: exit_codes # special mode that checks exit codes
    set_status: FAILED # set status FAILED, if unexpected exit codes
```

If you change this debug call for example to:
```c
debug(SYSCALL, "Bye I am out! Code: %zd\n", exit_code)
```
The pattern for the config entry for `exit_codes` has to be changed as well:
```yaml
    pattern: 'Bye I am out! Code: (\d+)'
```

#### More use cases

- If you are having problems with a specific component of your sweb, you can temporarily add logs from this component to
  error summaries. For example if you want to debug USERTHREAD logs, you could add the following entry to your config:

    ```yaml
      - name: userthread_logs
        scope: 'USERTHREAD'
        pattern: '(.*)'
        mode: add_as_error

    ```
- `tortillas_expect` is a sweb userspace function, which allows you to assert stuff to be printed via Syscall::write at runtime. You probably won't need that, but it is something we used.

  For example:
  ```cpp
  #define NUM 100
  int main()
  {
    // Declare something to be expected at runtime
    tortillas_expect("%d\n", NUM);

    printf("%d\n", NUM)
  }
  ```

  <details><summary>Implementation and config entry</summary>

    ### Introduce `tortillas_expect`

    ```diff
    diff --git a/userspace/libc/include/assert.h b/userspace/libc/include/assert.h
    index 20e488f4..50e93c6b 100644
    --- a/userspace/libc/include/assert.h
    +++ b/userspace/libc/include/assert.h
    @@ -7,3 +7,8 @@
         printf("Assertion failed: '%s', file %s, function %s, line %d\n", #X, __FILE__, __FUNCTION__, __LINE__); \
      exit(-1); } } while (0)

    +/*
    +* Wrapper around printf. Everything, that gets printed with this gets
    +* prefixed with 'TORTILLAS EXPECT: '.
    +**/
    +#define tortillas_expect(FMT, ...) printf("TORTILLAS EXPECT: " FMT, __VA_ARGS__);
    ```
    ### Config entry

    ```yaml
    # Tortillas expect
      - name: expect_stdout
        scope: SYSCALL
        pattern: 'Syscall::write: (.*)'
        mode: expect_stdout
        set_status: FAILED
    ```

  </details>


### Supported fields in `tortillas-config.yml`:

- `threads: int` - Number of tests to run in parallel
- `bootup_timeout_secs: int` - Seconds until bootup timeout
- `default_test_timeout_secs: int` - Seconds until test timeout (default)
- `sc_tortillas_bootup: int` - A syscall number signaling bootup
- `sc_tortillas_finished: int` - A syscall number signaling test completion
- `analyze` - List of analyze config entries

#### Analyze config entry

- `name: str` - Unique identifier for matching logs.
- `scope: str` - Debug log identifier (e.g. SYSCALL, THREAD,... as used in `debug(SYSCALL, ...);`) or 'ALL'
- `pattern: str` - Regex pattern to match.
- `mode: str` - Options:
    - `add_as_error` - Each match will be added to the error summary
    - `add_as_error_join` - Matches will be joined and added to the error summary as a code block.
    - `add_as_error_last` - Add the last occurrence of the pattern to the error_summary (Can be used to print the last pagefault)
    - `retry` - Retry the test, if matched. (Only recommended for debugging shenanigans)
    - `exit_codes` - _Special:_ entry needs to parse exit codes.
    - `expect_stdout` - _Special:_ specifically for `tortillas_expect`, entry needs to parse stdout (`Syscall::write: (.*)` in base-sweb).

###### Optional
- `set_status: str` - If the entry matches something in the logs, apply this status to the test. Options:
    - `PANIC`
    - `FAILED`

## Test specifications
```yaml
/*
---
category: pthread
description: "Create a single thread, then exit"
*/
```

Tortillas requires a test header in yaml format, that contains information about
the test and configurations of the test, if needed.
Reason for making it required is to force you to describe your tests.

A nice side effect of this is, that you can compile all your specifications into a summary of all your tests at the end of an assignment. Currently this is done by [`salsa.py`](salsa.py), but it would be cool to integrate it into tortillas.

We can also directly specify test behavior in test specifications.
For example:

- `expect_exit_codes: [1237619379]` will make the test fail, if it does not exit with `1237619379`. (This supports multiple values for situations with fork and multiple exit codes)
- `timeout: 240` will overwrite the default timeout to be 4 minutes (default is set in `tortillas_config.yml`).

### Supported fields:

###### Required

- `category: str` - category of the test
- `description: str` - test description

###### Optional

- `tags: list[str]` - tags of the test
- `timeout: int` - test run timeout (in seconds)
- `expect_timeout: bool` - don't fail, if a timeout occurs
- `expect_exit_codes: list[int]` - what exit codes are expected (default: [0])
- `disabled: bool` - disable the test by setting this to true

### Header format
Tortillas tries to parse a test header under the following conditions:

- first line contains `/*`
- first or seconds line contains `---`

If those conditions are not met, tortillas will skip the file.
If they are met, lines until `*/` will be parsed as yaml and it will
complain about missing fields.

## How Tortillas works under the hood

### Interrupt/Syscall detection

Tortillas does not rely on the log output to determine bootup, test completion and kernel panics.
Instead it uses qemu interrupt logging to detect certain interrupts.
This is why you have to add syscalls to your sweb.

Using this approach has the following advantages:
- Detection does not rely on the `KprintfFlushingThread`
- Reliable detection of kernel panics (no more interrupts are coming)
- Also works, when there are multiple processes (due to `fork`)

#### Why not use `sc_write` to detect bootup and `sc_exit` to detect test completion?

This was the original solution. In fact, setting `sc_tortillas_bootup: 4` and `sc_tortillas_finished: 1` will probably work fine, until adding new features breaks it. That can occur, when `sc_write` is being called too far ahead of the shell being ready, or if multiple processes are involved.

### Procedure of running tests

1. Bootup sweb _(wait until the tortillas bootup syscall)_
2. Create a qemu snapshot and do `savevm`
3. Run all tests, by starting from the snapshot
5. Wait for test completion _(wait until the tortillas finished syscall)_

## Troubleshooting

#### Tortillas fails to detect an error

You probably changed a `debug()` call somewhere, or disabled a scope tortillas needs in `common/include/console/debug.h`.
Check your analyze entries in `tortillas_config.yml` and figure out what is not being detected.
See [Configure log handling _(You might need this)_](#configure-log-handling-you-might-need-this)

#### Frequent sweb mounting errors
The sweb IDEDriver currently sometimes fails to detect the idea drive. This produces the following PANIC: \
`KERNEL PANIC: Assertion !VfsSyscall::mount("idea1", "/usr", "minixfs", 0)`

A new IDEDriver is being worked on. Until then, you can try something like [this](https://github.com/PaideiaDilemma/tortillas-sweb/commit/c0fb4e985b9a070c5cfa2596f500681844df1bf2).

#### Multiple processes _(Known issue, pls fix)_

Once your sweb involves `fork`, an obvious problem arises: __The shell needs to block until the last process finished__, otherwise
tortillas will kill the test too early.

When you switch your shell to `fork+exec` and you do not have `waitpid` to block, detection of test completion will break.

##### Possible workarounds

- Implement a mode in tortillas, that keeps a count of running processes by counting `fork` and `sc_exit` syscalls and determine
  test completion that way.
- Add a test specification option to wait additional time after the shell signaled test completion.

## Contribute

If you encounter any bugs or have ideas for useful features, please consider contributing.
This project will only survive if students contribute and maintain it.

## License
See [LICENSE](LICENSE) _(GPLv3)_
