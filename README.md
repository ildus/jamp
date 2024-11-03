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

Installation and usage
-----------------------

    pip3 install github.com/ildus/jamp
    cd $src # to directory with Jamfile
    jamp # or python3 -m jamp
    ninja

OpenVMS notes
---------------

Use my `github.com/ildus/samurai` fork for compilation. It supports additional '$^' escape
sequence for newlines to allow adding full scripts to `build.ninja`.
