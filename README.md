Jam build system on Python
--------------------------

This is reimplementation of Jam build system
([link](https://swarm.workshop.perforce.com/projects/perforce_software-jam))
on Python.

Supported platforms: Linux (Unix), OpenVMS

Differences from original Jam
-----------------------------

* Can't build itself (requires `ninja`, `samurai` or other `ninja` compatible builder).
* `mkdir` is a builtin command, collects all created dirs to `dirs` target.
* Builtin rules are case-insensitive (Echo and ECHO are same).
* Regular expressions are Python based.
* `Clean` actions are ignored in favour of `ninja -t clean`.

Quick start
-----------

Install:

    # install jamp
    pip3 install github.com/ildus/jamp

    # install ninja using your package manager
    dnf install ninja
    # or pacman -Syu ninja

For example we have this directory structure with a library and a main executable, and the
main executable uses math functions:

    src
        main.c
    lib
        print.c
    include
        common.h

    Jamfile

Corresponding Jamfile:

    HDRS = "include" ; # include should be quoted, it's a keyword in Jam
    Library libprint : lib/print.c ;
    Main app : src/main.c ;
    LinkLibraries app : libprint ;
    LINKLIBS on app = -lm ;

So to get the executable we only need to run this commands:

    jamp && ninja

Look at the tests dir to see more complex usage examples.

Documentation
-------------

See the `docs` directory.

OpenVMS notes
---------------

Use my `github.com/ildus/samurai` fork for compilation. It supports additional '$^' escape
sequence for newlines to allow adding full scripts to `build.ninja`.
