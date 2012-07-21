@# Example input file for `run_tests.py'.
@# 
@# Original Author: David Banas
@# Original Date:   July 20, 2012
@# 
@# Copyright (c) 2012 David Banas; All rights reserved World wide.

<test>
    <name>@(name)</name>
    <result>Hello, World!</result>
    <description>A dummy test, used as an example of test file syntax.</description>
    <output>
        <block name="Example `text' block" type="text">
If this is working correctly,
this should have started on a new line.

There should be a blank line, above this one.
And you should see the Python logo, below:
        </block>
        <block name="Example `image' block" type="image">
            python_logo.png
        </block>
    </output>
</test>

