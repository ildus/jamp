# Jamp - Make(1) Redux

## USAGE

```
usage: jamp [-h] [-b] [-v] [-s {base,ripgrep,grep,none}] [-d {headers,depends,include,env} [{headers,depends,include,env} ...]] [-t TARGET] [-f JAMFILE] [-e ENV]

Jam Build System (Python version)

options:
  -h, --help            show this help message and exit
  -b, --build           call ninja
  -v, --verbose         verbose output
  -s, --search-type {base,ripgrep,grep,none}
                        headers search type (default is basic jam algorithm)
  -d, --debug {headers,depends,include,env} [{headers,depends,include,env} ...]
                        show headers
  -t, --target TARGET   limit target for debug info
  -f, --jamfile JAMFILE
                        specify jam file name
  -e, --env ENV         specify extra env variables
```

## Description

`Jam` is a program construction tool, like `make`.

`Jam` recursively builds target files from source files, using dependency information and updating actions expressed in the Jambase file, which is written in `Jam`'s own interpreted language. The default Jambase provides a boilerplate for common use, relying on a user-provided file "Jamfile" to enumerate actual targets and sources.

The Jambase is described in the [Jambase Reference](Jambase.md) and the document [Using Jamfiles and Jambase](Jamfile.md).

## OPERATION

`Jam` has three phases of operation: start-up, parsing, binding. At the end it constructs `build.ninja` which can be fed to `ninja` or `samurai`.

### Start-up

Upon start-up, `Jam` imports environment variable settings into `Jam` variables. Environment variables are split at blanks with each word becoming an element in the variable's list of values. Environment variables whose names end in PATH are split at $(SPLITPATH) characters (e.g., ":" for Unix).

To set a variable's value on the command line, overriding the variable's environment value, use the `-e` option. To see variable assignments made during `Jam`'s execution, use the `--debug env` option.

### Parsing

In the parsing phase, `Jam` reads and executes the Jambase file, by default the built-in one. It is written in the `Jam` language. See [Language](#language) below. The last action of the Jambase is to read (via the "include" rule) a user-provided file called "Jamfile".

Collectively, the purpose of the Jambase and the Jamfile is to name built target and source files, construct the dependency graph among them, and associate build actions with targets. The Jambase defines boilerplate rules and variable assignments, and the Jamfile uses these to specify the actual relationship among the target and source files. See the [Jambase Reference](Jambase.md) and the document [Using Jamfiles and Jambase](Jamfile.md) for information.

### Binding

After parsing, `Jam` recursively descends the dependency graph and binds every file target with a location in the filesystem.

### Targets

Any string value in `Jam` can represent a target, and it does so if the `Depends` or `Includes` rules make it part of the dependency graph. Build targets are files to be updated. Source targets are the files used in updating build targets. Build targets and source targets are collectively referred to as file targets, and frequently build targets are source targets for other build targets. Pseudotargets are symbols which represent dependencies on other targets, but which are not themselves associated with any real file.

A file target's identifier is generally the file's name, which can be absolutely rooted, relative to the directory of `Jam`'s invocation, or simply local (no directory). Most often it is the last case, and the actual file path is bound using the $(SEARCH) and $(LOCATE) special variables. See [SEARCH and LOCATE Variables](#search-and-locate-variables) below. A local filename is optionally qualified with "grist," a string value used to assure uniqueness. A file target with an identifier of the form *file(member)* is a library member (usually an ar(1) archive on UNIX).

The use of $(SEARCH) and $(LOCATE) allows `Jam` to separate the location of files from their names, so that Jamfiles can refer to files locally (i.e. relative to the Jamfile's directory), yet still be usable when `Jam` is invoked from a distant directory. The use of grist allows files with the same name to be identified uniquely, so that `Jam` can read a whole directory tree of Jamfiles and not mix up same-named targets.

### Update Determination

After binding each target, `Jam` determines whether the target needs updating, and if so marks the target for the updating phase. A target is normally so marked if it is missing, it is older than any of its sources, or any of its sources are marked for updating. This behavior can be modified by the application of special built-in rules. See [Modifying Binding](#modifying-binding) below.

### Header File Scanning

During the binding phase, `Jam` also performs header file scanning, where it looks inside source files for the implicit dependencies on other files caused by C's #include syntax. This is controlled by the special variables $(HDRSCAN) and $(HDRRULE). The result of the scan is formed into a rule invocation, with the scanned file as the target and the found included file names as the sources. Note that this is the only case where rules are invoked outside the parsing phase. See [HDRSCAN and HDRRULE Variables](#hdrscan-and-hdrrule-variables) below.

### Updating

After binding, `Jam` again recursively descends the dependency graph, this time executing the update actions for each target marked for update during the binding phase. If a target's updating actions fail, then all other targets which depend on that target are skipped.

The -j flag instructs `Jam` to build more than one target at a time. If there are multiple actions on a single target, they are run sequentially. The -g flag reorders builds so that targets with newest sources are built first. Normally, they are built in the order of appearance in the Jamfiles.

## LANGUAGE

### Overview

`Jam` has an interpreted, procedural language with a few select features to effect program construction. Statements in `Jam` are rule (procedure) definitions, rule invocations, updating action definitions, flow-of-control structures, variable assignments, and sundry language support.

### Lexical Features

`Jam` treats its input files as whitespace-separated tokens, with two exceptions: double quotes (") can enclose whitespace to embed it into a token, and everything between the matching curly braces ({}) in the definition of a updating actions is treated as a single string. A backslash (\\) can escape a double quote, or any single whitespace character.

`Jam` requires whitespace (blanks, tabs, or newlines) to surround all tokens, **including the colon (:) and semicolon (;) tokens**.

`Jam` keywords (as mentioned in this document) are reserved and generally must be quoted with double quotes (") to be used as arbitrary tokens, such as variable or target names.

### Datatype

`Jam`'s only data type is a one-dimensional list of arbitrary strings. They arise as literal (whitespace-separated) tokens in the Jambase or included files, as the result of variable expansion of those tokens, or as the return value from a rule invocation.

### Rules

The basic `Jam` language entity is called a rule. A rule is simply a procedure definition, with a body of `Jam` statements to be run when the rule is invoked. The syntax of rule invocation makes it possible to write Jamfiles that look a bit like Makefiles.

Rules take up to 9 arguments ($(1) through $(9), each a list) and can have a return value (a single list). A rule's return value can be expanded in a list by enclosing the rule invocation with `[` and `]`.

### Updating Actions

A rule may have updating actions associated with it, in which case arguments $(1) and $(2) are treated as built targets and sources, respectively. Updating actions are the OS shell commands to execute when updating the built targets of the rule.

When a rule with updating actions is invoked, those actions are added to those associated with its built targets ($(1)) before the rule's procedure is run. Later, to build the targets in the updating phase, the actions are passed to the OS command shell, with $(1) and $(2) replaced by bound versions of the target names. See [Binding](#binding) above.

### Statements

`Jam`'s language has the following statements:

`rulename field1 : field2 : ... : fieldN ;`

Invoke a rule. A rule is invoked with values in *field1* through *fieldN* (9 max). They may be referenced in the procedure's *statements* as $(1) through $(N). $(<) and $(>) are synonymous with $(1) and $(2).

*rulename* undergoes [variable expansion](#variable-expansion). If the resulting list is more than one value, each rule is invoked with the same arguments, and the result of the invocation is the concatenation of all the results.

`actions [ modifiers ] rulename { commands }`

Define a rule's updating actions, replacing any previous definition. The first two arguments may be referenced in the action's *commands* as $(1) and $(2) or $(<) and $(>).

The following action *modifiers* are understood:

`actions bind vars` $(vars) will be replaced with bound values.
`actions existing` $(>) includes only source targets currently existing.
`actions ignore` The return status of the *commands* is ignored.
`actions piecemeal` *commands* are repeatedly invoked with a subset of $(>) small enough to fit in the command buffer on this OS.
`actions quietly` The action is not echoed to the standard output.
`actions together` The $(>) from multiple invocations of the same action on the same built target are glommed together.
`actions updated` $(>) includes only source targets themselves marked for updating.

`break`

Breaks out of the closest enclosing *for* or *while* loop.

`continue`

Jumps to the end of the closest enclosing *for* or *while* loop.

`for var in list { statements }`

Executes *statements* for each element in *list*, setting the variable *var* to the element value.

`if cond { statements } [ else statements ]`

Does the obvious; the else clause is optional. *cond* is built of:

`a` true if any *a* element is a non-zero-length string
`a = b` list *a* matches list *b* string-for-string
`a != b` list *a* does not match list *b*
`a < b` *a[i]* string is less than *b[i]* string, where *i* is first mismatched element in lists *a* and *b*
`a <= b` every *a* string is less than or equal to its *b* counterpart
`a > b` *a[i]* string is greater than *b[i]* string, where *i* is first mismatched element
`a >= b` every *a* string is greater than or equal to its *b* counterpart
`a in b` true if all elements of *a* can be found in *b*, or if *a* has no elements
`! cond` condition not true
`cond && cond` conjunction
`cond || cond` disjunction
`( cond )` precedence grouping

`include file ;`

Causes `Jam` to read the named *file*. The file is bound like a regular target (see [Binding](#binding) above) but unlike a regular target the include file cannot be built. Marking an include file target with the **NOCARE** rule makes it optional: if it is missing, it causes no error.

The include file is inserted into the input stream during the parsing phase. The primary input file and all the included file(s) are treated as a single file; that is, `Jam` infers no scope boundaries from included files.

`local vars [ = values ] ;`

Creates new *vars* inside to the enclosing {} block, obscuring any previous values they might have. The previous values for *vars* are restored when the current block ends. Any rule called or file included will see the local and not the previous value (this is sometimes called Dynamic Scoping). The local statement may appear anywhere, even outside of a block (in which case the previous value is restored when the input ends). The *vars* are initialized to *values* if present, or left uninitialized otherwise.

`on target statement ;`

Run *statement* under the influence of *target*'s target-specific variables. These variables become local copies during *statement*'s run, but they may be updated as target-specific variables using the usual "*variable* on *targets* =" syntax.

`return values ;`

Within a rule body, the return statement sets the return value for an invocation of the rule and terminates the rule's execution.

`rule rulename [ : vars ] { statements }`

Define a rule's procedure, replacing any previous definition. If *vars* are provided, they are assigned the values of the parameters ($(1) to $(9)) when *statements* are executed, as with the **local** statement.

`switch value { case pattern1 : statements ; case pattern2 : statements ; ... }`

The switch statement executes zero or one of the enclosed *statements*, depending on which, if any, is the first case whose *pattern* matches *value*. The *pattern* values are not variable-expanded. The *pattern* values may include the following wildcards:

`?` match any single character
`*` match zero or more characters
`[chars]` match any single character in *chars*
`[^chars]` match any single character not in *chars*
`\x` match *x* (escapes the other wildcards)

`while cond { statements }`

Repeatedly execute *statements* while *cond* remains true upon entry. (See the description of *cond* expression syntax under [if](#if), above).

### Variables

`Jam` variables are lists of zero or more elements, with each element being a string value. An undefined variable is indistinguishable from a variable with an empty list, however, a defined variable may have one more elements which are null strings. All variables are referenced as $(*variable*).

Variables are either global or target-specific. In the latter case, the variable takes on the given value only during the target's binding, header file scanning, and updating; and during the "on *target* *statement*" statement.

A variable is defined with:

`variable = elements ;`

`variable += elements ;`

`variable ?= elements ;`

`variable on targets = elements ;`

`variable on targets += elements ;`

`variable on targets ?= elements ;`

The first three forms set *variable* globally. The last three forms set a target-specific variable. The = operator replaces any previous elements of *variable* with *elements*; the += operation adds *elements* to *variable*'s list of elements; the ?= operator sets *variable* only if it was previously unset. The last form "*variable* on *targets* ?= *elements*" checks to see if the target-specific, not the global, variable is set. (The ?= operator also has an old form "default =".)

Variables referenced in updating commands will be replaced with their values; target-specific values take precedence over global values. Variables passed as arguments ($(1) and $(2)) to actions are replaced with their bound values; the "bind" modifier can be used on actions to cause other variables to be replaced with bound values. See [Action Modifiers](#action-modifiers) above.

`Jam` variables are not re-exported to the environment of the shell that executes the updating actions, but the updating actions can reference `Jam` variables with $(*variable*).

## Variable Expansion

During parsing, `Jam` performs variable expansion on each token that is not a keyword or rule name. Such tokens with embedded variable references are replaced with zero or more tokens. Variable references are of the form $(*v*) or $(*vm*), where *v* is the variable name, and *m* are optional modifiers.

Variable expansion in a rule's actions is similar to variable expansion in statements, except that the action string is tokenized at whitespace regardless of quoting.

The result of a token after variable expansion is the *product* of the components of the token, where each component is a literal substring or a list substituting a variable reference. For example:

```
$(X) -> a b c 
t$(X) -> ta tb tc 
$(X)z -> az bz cz 
$(X)-$(X) -> a-a a-b a-c b-a b-b b-c c-a c-b c-c
```

The variable name and modifiers can themselves contain a variable reference, and this partakes of the product as well:

```
$(X) -> a b c 
$(Y) -> 1 2 
$(Z) -> X Y 
$($(Z)) -> a b c 1 2
```

Because of this product expansion, if any variable reference in a token is undefined, the result of the expansion is an empty list. If any variable element is a null string, the result propagates the non-null elements:

```
$(X) -> a "" 
$(Y) -> "" 1 
$(Z) -> 
*$(X)$(Y)* -> *a* *a1* ** *1* 
*$(X)$(Z)* ->
```

A variable element's string value can be parsed into grist and filename-related components. Modifiers to a variable are used to select elements, select components, and replace components. The modifiers are:

`[n]` Select element number *n* (starting at 1). If the variable contains fewer than *n* elements, the result is a zero-element list.
`[n-m]` Select elements number *n* through *m*.
`[n-]` Select elements number *n* through the last.
`:B` Select filename base.
`:S` Select (last) filename suffix.
`:M` Select archive member name.
`:D` Select directory path.
`:P` Select parent directory.
`:G` Select grist.
`:U` Replace lowercase characters with uppercase.
`:L` Replace uppercase characters with lowercase.
`:chars` Select the components listed in *chars*.
`:G=grist` Replace grist with *grist*.
`:D=path` Replace directory with *path*.
`:B=base` Replace the base part of file name with *base*.
`:S=suf` Replace the suffix of file name with *suf*.
`:M=mem` Replace the archive member name with *mem*.
`:R=root` Prepend *root* to the whole file name, if not already rooted.
`:E=value` Use *value* instead if the variable is unset.
`:J=joinval` Concatenate list elements into single element, separated by *joinval*.

On VMS, $(var:P) is the parent directory of $(var:D); on Unix and NT, $(var:P) and $(var:D) are the same.

### Built-in Rules

`Jam` has twelve built-in rules, all of which are pure procedure rules without updating actions. They are in three groups: the first builds the dependency graph; the second modifies it; and the third are just utility rules.

#### Dependency Building

`DEPENDS targets1 : targets2 ;`

Builds a direct dependency: makes each of *targets1* depend on each of *targets2*. Generally, *targets1* will be rebuilt if *targets2* are themselves rebuilt are or are newer than *targets1*.

`INCLUDES targets1 : targets2 ;`

Builds a sibling dependency: makes any target that depends on any of *targets1* also depend on each of *targets2*. This reflects the dependencies that arise when one source file includes another: the object built from the source file depends both on the original and included source file, but the two sources files don't depend on each other. For example:

```
DEPENDS foo.o : foo.c ;
INCLUDES foo.c : foo.h ;
```

"foo.o" depends on "foo.c" and "foo.h" in this example.

#### Modifying Binding

The six rules ALWAYS, LEAVES, NOCARE, NOTFILE, NOUPDATE, and TEMPORARY modify the dependency graph so that `Jam` treats the targets differently during its target binding phase. See [Binding](#binding) above. Normally, `Jam` updates a target if it is missing, if its filesystem modification time is older than any of its dependencies (recursively), or if any of its dependencies are being updated. This basic behavior can be changed by invoking the following rules:

`ALWAYS targets ;`

Causes *targets* to be rebuilt regardless of whether they are up-to-date (they must still be in the dependency graph). This is used for the clean and uninstall targets, as they have no dependencies and would otherwise appear never to need building. It is best applied to targets that are also NOTFILE targets, but it can also be used to force a real file to be updated as well.

`LEAVES targets ;`

Makes each of *targets* depend only on its leaf sources, and not on any intermediate targets. This makes it immune to its dependencies being updated, as the "leaf" dependencies are those without their own dependencies and without updating actions. This allows a target to be updated only if original source files change.

`NOCARE targets ;`

Causes `Jam` to ignore *targets* that neither can be found nor have updating actions to build them. Normally for such targets `Jam` issues a warning and then skips other targets that depend on these missing targets. The HdrRule in Jambase uses NOCARE on the header file names found during header file scanning, to let `Jam` know that the included files may not exist. For example, if a #include is within an #ifdef, the included file may not actually be around.

`NOTFILE targets ;`

Marks *targets* as pseudotargets and not real files. No timestamp is checked, and so the actions on such a target are only executed if the target's dependencies are updated, or if the target is also marked with ALWAYS. The default `Jam` target "all" is a pseudotarget. In Jambase, NOTFILE is used to define several addition convenient pseudotargets.

`NOUPDATE targets ;`

Causes the timestamps on *targets* to be ignored. This has two effects: first, once the target has been created it will never be updated; second, manually updating target will not cause other targets to be updated. In Jambase, for example, this rule is applied to directories by the MkDir rule, because MkDir only cares that the target directory exists, not when it has last been updated.

`TEMPORARY targets ;`

Marks *targets* as temporary, allowing them to be removed after other targets that depend upon them have been updated. If a TEMPORARY target is missing, `Jam` uses the timestamp of the target's parent. Jambase uses TEMPORARY to mark object files that are archived in a library after they are built, so that they can be deleted after they are archived.

#### Utility Rules

The remaining rules are utility rules.

`ECHO args ; Echo args ; echo args ;`

Blurts out the message *args* to stdout.

`EXIT args ; Exit args ; exit args ;`

Blurts out the message *args* to stdout and then exits with a failure status.

`GLOB directories : patterns ;`

Scans *directories* for files matching *patterns*, returning the list of matching files (with directory prepended). *patterns* uses the same syntax as in the **switch** statement. Only useful within the `[ ]` construct, to change the result into a list.

`MATCH regexps : list ;`

Matches the **egrep**(1) style regular expressions *regexps* against the strings in *list*. The result is the concatenation of matching `()` subexpressions for each string in *list*, and for each regular expression in *regexps*. Only useful within the `[ ]` construct, to change the result into a list.

### Built-in Variables

This section discusses variables that have special meaning to `Jam`.

#### SEARCH and LOCATE Variables

These two variables control the binding of file target names to locations in the file system. Generally, $(SEARCH) is used to find existing sources while $(LOCATE) is used to fix the location for built targets.

Rooted (absolute path) file targets are bound as is. Unrooted file target names are also normally bound as is, and thus relative to the current directory, but the settings of $(LOCATE) and $(SEARCH) alter this:

- If $(LOCATE) is set then the target is bound relative to the first directory in $(LOCATE). Only the first element is used for binding.
- If $(SEARCH) is set then the target is bound to the first directory in $(SEARCH) where the target file already exists.
- If the $(SEARCH) search fails, the target is bound relative to the current directory anyhow.

Both $(SEARCH) and $(LOCATE) should be set target-specific and not globally. If they were set globally, `Jam` would use the same paths for all file binding, which is not likely to produce sane results. When writing your own rules, especially ones not built upon those in Jambase, you may need to set $(SEARCH) or $(LOCATE) directly. Almost all of the rules defined in Jambase set $(SEARCH) and $(LOCATE) to sensible values for sources they are looking for and targets they create, respectively.

#### HDRSCAN and HDRRULE Variables

These two variables control header file scanning. $(HDRSCAN) is an **egrep**(1) pattern, with ()'s surrounding the file name, used to find file inclusion statements in source files. Jambase uses $(HDRPATTERN) as the pattern for $(HDRSCAN). $(HDRRULE) is the name of a rule to invoke with the results of the scan: the scanned file is the target, the found files are the sources. $(HDRRULE) is run under the influence of the scanned file's target-specific variables.

Both $(HDRSCAN) and $(HDRRULE) must be set for header file scanning to take place, and they should be set target-specific and not globally. If they were set globally, all files, including executables and libraries, would be scanned for header file include statements.

The scanning for header file inclusions is not exact, but it is at least dynamic, so there is no need to run something like **makedepend**(GNU) to create a static dependency file. The scanning mechanism errs on the side of inclusion (i.e., it is more likely to return filenames that are not actually used by the compiler than to miss include files) because it can't tell if #include lines are inside #ifdefs or other conditional logic. In Jambase, HdrRule applies the NOCARE rule to each header file found during scanning so that if the file isn't present yet doesn't cause the compilation to fail, `Jam` won't care.

Also, scanning for regular expressions only works where the included file name is literally in the source file. It can't handle languages that allow including files using variable names (as the Jam language itself does).

#### Platform Identifier Variables

A number of Jam built-in variables can be used to identify runtime platform:

| Variable | Description |
|----------|-------------|
| OS       | OS identifier string |
| OSPLAT   | Underlying architecture, when applicable |
| MAC      | true on MAC platform |
| NT       | true on NT platform |
| OS2      | true on OS2 platform |
| UNIX     | true on Unix platforms |
| VMS      | true on VMS platform |

#### Jam Version Variables

| Variable    | Description |
|-------------|-------------|
| JAMDATE     | Time and date at `Jam` start-up |
| JAMUNAME    | Output of **uname**(1) command (Unix only) |
| JAMVERSION  | `Jam` version, as reported by jam -v |

#### JAMSHELL Variable

When `Jam` executes a rule's action block, it forks and execs a shell, passing the action block as an argument to the shell. The invocation of the shell can be controlled by $(JAMSHELL). The default on Unix is, for example:

`JAMSHELL = /bin/sh -c % ;`

The % is replaced with the text of the action block.

`Jam` does not directly support building in parallel across multiple hosts, since that is heavily dependent on the local environment. To build in parallel across multiple hosts, you need to write your own shell that provides access to the multiple hosts. You then reset $(JAMSHELL) to reference it.

Just as `Jam` expands a % to be the text of the rule's action block, it expands a ! to be the multi-process slot number. The slot number varies between 1 and the number of concurrent jobs permitted by the -j flag given on the command line. Armed with this, it is possible to write a multiple host shell. For example:

```
#!/bin/sh
# This sample JAMSHELL uses the SunOS on(1) command to execute a
# command string with an identical environment on another host.
# Set JAMSHELL = jamshell ! %
#
# where jamshell is the name of this shell file.
#
# This version handles up to -j6; after that they get executed
# locally.
case $1 in
1|4) on winken sh -c "$2";;
2|5) on blinken sh -c "$2";;
3|6) on nod sh -c "$2";;
*) eval "$2";;
esac
```

## SEE ALSO

- [Jambase Reference](Jambase.md)
- [Using Jamfiles and Jambase](Jamfile.md)

## Credits

The doc is copied and modified from the original Jam.html.

Jam's author is Christopher Seiwald ([seiwald@perforce.com](mailto:seiwald@perforce.com)).
Documentation is provided by [Perforce Software, Inc.](http://www.perforce.com)

* * *

The original [Jam](http://www.perforce.com/jam/jam.html) Executable
Copyright 1993-2002 Christopher Seiwald and Perforce Software, Inc.
