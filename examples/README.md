# Base example

Here are some example diffs of how to set up tortillas.

:link: [Source](https://github.com/PaideiaDilemma/tortillas-sweb)

## No grub boot menu

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

## Meta syscalls

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
## Add mult.c test specification

```diff
diff --git a/userspace/tests/mult.c b/userspace/tests/mult.c
index fd27b643..674d2be0 100644
--- a/userspace/tests/mult.c
+++ b/userspace/tests/mult.c
@@ -1,3 +1,12 @@
+/*
+--- # Test specification
+category: base
+description: |
+    Multiplies two matrices containing pseudo random numbers
+    and exits with the sum of the resulting matrix.
+expect_exit_codes: [1237619379]
+*/
+
 #include "../../common/include/kernel/syscall-definitions.h"


```
# Extended example

:link: [Source](https://github.com/PaideiaDilemma/tortillas-sweb/tree/extended)

## Add `tortillas_expect`

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

## Example test for tortillas-expect

```c
/*
---
category: tortillas
description: "This test demonstrates tortillas_expect."
*/

#include "stdio.h"
#include "assert.h"

#define ITERS 50

int count = 0;

void task()
{
  printf("count %d\n", count);
  count++;
}

int main()
{
  for (int i = 0; i < ITERS; i++)
    tortillas_expect("count %d\n", i);

  for (int i = 0; i < ITERS; i++)
    task();
}
```
# Panic example

Triggers different errors, to demonstrate how tortillas handles them.

:link: [Source](https://github.com/PaideiaDilemma/tortillas-sweb/tree/extended)

## Add some panic

```diff
diff --git a/common/source/kernel/Syscall.cpp b/common/source/kernel/Syscall.cpp
index 10e10a31..2fbeb991 100644
--- a/common/source/kernel/Syscall.cpp
+++ b/common/source/kernel/Syscall.cpp
@@ -7,6 +7,7 @@
 #include "UserProcess.h"
 #include "ProcessRegistry.h"
 #include "File.h"
+#include "SpinLock.h"

 size_t Syscall::syscallException(size_t syscall_number, size_t arg1, size_t arg2, size_t arg3, size_t arg4, size_t arg5)
 {
@@ -67,6 +68,15 @@ void Syscall::pseudols(const char *pathname, char *buffer, size_t size)

 void Syscall::exit(size_t exit_code)
 {
+  if (exit_code == 1)
+  {
+    assert(false);
+  }
+  if (exit_code == 2)
+  {
+    SpinLock lock("");
+    lock.release();
+  }
   debug(SYSCALL, "Syscall::EXIT: called, exit_code: %zd\n", exit_code);
   currentThread->kill();
 }
```

## Failing demo tests

### panic1 test

```c
/*
---
category: panic
description: "Dummy test, to demo a kernel panic triggered by exit(1)"
*/

#include "stdlib.h"

int main()
{
  exit(1);
}
```


### panic2 test

```c
/*
---
category: panic
description: "Dummy test, to demo a locking error triggered by exit(2)"
*/

#include "stdlib.h"

int main()
{
  exit(2);
}
```

### Bad exit code

```c
/*
---
category: panic
description: "Dummy test, to demo wrong exit code"
*/

#include "stdlib.h"

int main()
{
  exit(3);
}
```

### timeout test

```c
/*
---
category: panic
description: "Dummy test, to demo a test timeout"
timeout: 20
*/

#include "stdlib.h"
#include "sched.h"

int main()
{
  while (1)
    sched_yield();
}
```

### unknown-command test

```c
/*
---
category: panic
description: "Dummy test, to demo unknown command, when the test name contains an underscore"
*/

#include "stdlib.h"

int main()
{
}
```

### userspace-assert test

```c
/*
---
category: panic
description: "Dummy test, to demo userspace asserts"
*/

#include "assert.h"

int main()
{
  assert(1==2);
}
```
