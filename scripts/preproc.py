#!/usr/bin/python3
#--------------------------------------------------------------------
#
# preproc.py
#
# General purpose macro preprocessor
#
#--------------------------------------------------------------------
# Usage:
#
#	preproc.py input_file [output_file] [-D<variable> ...]
#
# Where <variable> may be a keyword or a key=value pair
#
# Syntax:  Basically like cpp.  However, this preprocessor handles
# only a limited set of keywords, so it does not otherwise mangle
# the file in the belief that it must be C code.  Handling of boolean
# relations is important, so these are thoroughly defined (see below)
#
#	#if defined(<variable>) [...]
#	#ifdef <variable>
#	#ifndef <variable>
#	#elseif <variable>
#	#else
#	#endif
#
#	#define <variable> [...]
#	#undef <variable>
#
#	#include <filename>
#
# <variable> may be
#	<keyword>
#	<keyword>=<value>
#
#	<keyword> without '=' is effectively the same as <keyword>=1
#	Lack of a keyword is equivalent to <keyword>=0, in a conditional.
#
# Boolean operators (in order of precedence):
#	!	NOT
#	&&	AND
#	||	OR	
#
# Comments:
#       Most comments (C-like or Tcl-like) are output as-is.  A
#	line beginning with "###" is treated as a preprocessor
#	comment and is not copied to the output.
#
# Examples;
#	#if defined(X) || defined(Y)
#	#else
#	#if defined(Z)
#	#endif
#--------------------------------------------------------------------

import re
import sys

def solve_statement(condition):

    defrex = re.compile('defined[ \t]*\(([^\)]+)\)')
    orrex = re.compile('(.+)\|\|(.+)')
    andrex = re.compile('(.+)&&(.+)')
    notrex = re.compile('!([^&\|]+)')
    parenrex = re.compile('\(([^\)]+)\)')
    leadspacerex = re.compile('^[ \t]+(.*)')
    endspacerex = re.compile('(.*)[ \t]+$')

    matchfound = True
    while matchfound:
        matchfound = False

        # Search for defined(K) (K must be a single keyword)
        # If the keyword was defined, then it should have been replaced by 1
        lmatch = defrex.search(condition)
        if lmatch:
            key = lmatch.group(1)
            if key == 1 or key == '1' or key == True:
                repl = 1
            else:
                repl = 0

            condition = defrex.sub(str(repl), condition)
            matchfound = True

        # Search for (X) recursively
        lmatch = parenrex.search(condition)
        if lmatch:
            repl = solve_statement(lmatch.group(1))
            condition = parenrex.sub(str(repl), condition)
            matchfound = True

        # Search for !X recursively
        lmatch = notrex.search(condition)
        if lmatch:
            only = solve_statement(lmatch.group(1))
            if only == '1':
                repl = '0'
            else:
                repl = '1'
            condition = notrex.sub(str(repl), condition)
            matchfound = True

        # Search for A&&B recursively
        lmatch = andrex.search(condition)
        if lmatch:
            first = solve_statement(lmatch.group(1))
            second = solve_statement(lmatch.group(2))
            if first == '1' and second == '1':
                repl = '1'
            else:
                repl = '0'
            condition = andrex.sub(str(repl), condition)
            matchfound = True

        # Search for A||B recursively
        lmatch = orrex.search(condition)
        if lmatch:
            first = solve_statement(lmatch.group(1))
            second = solve_statement(lmatch.group(2))
            if first == '1' or second == '1':
                repl = '1'
            else:
                repl = '0'
            condition = orrex.sub(str(repl), condition)
            matchfound = True
 
    # Remove whitespace
    lmatch = leadspacerex.match(condition)
    if lmatch:
        condition = lmatch.group(1)
    lmatch = endspacerex.match(condition)
    if lmatch:
        condition = lmatch.group(1)
    
    return condition

def solve_condition(condition, keys, defines, keyrex):
    # Do definition replacement on the conditional
    for keyword in keys:
        condition = keyrex[keyword].sub(defines[keyword], condition)

    value = solve_statement(condition)
    if value == '1':
        return 1
    else:
        return 0

def runpp(keys, keyrex, defines, ccomm, incdirs, inputfile, ofile):

    includerex = re.compile('^[ \t]*#include[ \t]+"*([^ \t\n\r"]+)')
    definerex = re.compile('^[ \t]*#define[ \t]+([^ \t]+)[ \t]+(.+)')
    defrex = re.compile('^[ \t]*#define[ \t]+([^ \t\n\r]+)')
    undefrex = re.compile('^[ \t]*#undef[ \t]+([^ \t\n\r]+)')
    ifdefrex = re.compile('^[ \t]*#ifdef[ \t]+(.+)')
    ifndefrex = re.compile('^[ \t]*#ifndef[ \t]+(.+)')
    ifrex = re.compile('^[ \t]*#if[ \t]+(.+)')
    elseifrex = re.compile('^[ \t]*#elseif[ \t]+(.+)')
    elserex = re.compile('^[ \t]*#else')
    endifrex = re.compile('^[ \t]*#endif')
    commentrex = re.compile('^###[^#]*$')
    ccstartrex = re.compile('/\*')		# C-style comment start
    ccendrex = re.compile('\*/')			# C-style comment end

    badifrex = re.compile('^[ \t]*#if[ \t]*.*')
    badelserex = re.compile('^[ \t]*#else[ \t]*.*')

    # This code is not designed to operate on huge files.  Neither is it designed to be
    # efficient.

    # ifblock state:
    # -1 : not in an if/else block
    #  0 : no condition satisfied yet
    #  1 : condition satisfied
    #  2 : condition was handled, waiting for endif

    ifile = False
    try:
        ifile = open(inputfile, 'r')
    except FileNotFoundError:
        for dir in incdirs:
            try:
                ifile = open(dir + '/' + inputfile, 'r')
            except FileNotFoundError:
                pass
            else:
                break

    if not ifile:
        print("Error:  Cannot open file " + inputfile + " for reading.\n")
        return

    ccblock = -1
    ifblock = -1
    ifstack = []
    lineno = 0

    filetext = ifile.readlines()
    for line in filetext:
        lineno += 1

        # C-style comments override everything else
        if ccomm:
            if ccblock == -1:
                pmatch = ccstartrex.search(line)
                if pmatch:
                    ematch = ccendrex.search(line[pmatch.end(0):])
                    if ematch:
                        line = line[0:pmatch.start(0)] + line[ematch.end(0)+2:]
                    else:
                        line = line[0:pmatch.start(0)]
                        ccblock = 1
            elif ccblock == 1:
                ematch = ccendrex.search(line)
                if ematch:
                    line = line[ematch.end(0)+2:]
                    ccblock = -1
                else:
                    continue

        # Ignore lines beginning with "###"
        pmatch = commentrex.match(line)
        if pmatch:
            continue

        # Handle include.  Note that this code does not expect or
        # handle 'if' blocks that cross file boundaries.
        pmatch = includerex.match(line)
        if pmatch:
            inclfile = pmatch.group(1)
            runpp(keys, keyrex, defines, ccomm, incdirs, inclfile, ofile)
            continue

        # Handle define (with value)
        pmatch = definerex.match(line)
        if pmatch:
            condition = pmatch.group(1)
            value = pmatch.group(2)
            defines[condition] = value
            keyrex[condition] = re.compile(condition)
            if condition not in keys:
                keys.append(condition)
            continue

        # Handle define (simple case, no value)
        pmatch = defrex.match(line)
        if pmatch:
            condition = pmatch.group(1)
            print("Defrex condition is " + condition)
            defines[condition] = '1'
            keyrex[condition] = re.compile(condition)
            if condition not in keys:
                keys.append(condition)
            print("Defrex value is " + defines[condition])
            continue

        # Handle undef
        pmatch = undefrex.match(line)
        if pmatch:
            condition = pmatch.group(1)
            if condition in keys:
                defines.pop(condition)
                keyrex.pop(condition)
                keys.remove(condition)
            continue

        # Handle ifdef
        pmatch = ifdefrex.match(line)
        if pmatch:
            if ifblock != -1:
                ifstack.append(ifblock)
                
            if ifblock == 1 or ifblock == -1:
                condition = pmatch.group(1)
                ifblock = solve_condition(condition, keys, defines, keyrex)
            else:
                ifblock = 2
            continue

        # Handle ifndef
        pmatch = ifndefrex.match(line)
        if pmatch:
            if ifblock != -1:
                ifstack.append(ifblock)
                
            if ifblock == 1 or ifblock == -1:
                condition = pmatch.group(1)
                ifblock = solve_condition(condition, keys, defines, keyrex)
                ifblock = 1 if ifblock == 0 else 0
            else:
                ifblock = 2
            continue

        # Handle if
        pmatch = ifrex.match(line)
        if pmatch:
            if ifblock != -1:
                ifstack.append(ifblock)

            if ifblock == 1 or ifblock == -1:
                condition = pmatch.group(1)
                ifblock = solve_condition(condition, keys, defines, keyrex)
            else:
                ifblock = 2
            continue

        # Handle elseif
        pmatch = elseifrex.match(line)
        if pmatch:
            if ifblock == -1:
               print("Error: #elseif without preceding #if at line " + str(lineno) + ".")
               ifblock = 0

            if ifblock == 1:
                ifblock = 2
            elif ifblock != 2:
                condition = pmatch.group(1)
                ifblock = solve_condition(condition, keys, defines, keyrex)
            continue

        # Handle else
        pmatch = elserex.match(line)
        if pmatch:
            if ifblock == -1:
               print("Error: #else without preceding #if at line " + str(lineno) + ".")
               ifblock = 0

            if ifblock == 1:
                ifblock = 2
            elif ifblock == 0:
                ifblock = 1
            continue

        # Handle endif
        pmatch = endifrex.match(line)
        if pmatch:
            if ifblock == -1:
                print("Error:  #endif outside of #if block at line " + str(lineno) + " (ignored)")
            elif ifstack:
                ifblock = ifstack.pop()
            else:
                ifblock = -1
            continue
                 
        # Check for 'if' or 'else' that were not properly formed
        pmatch = badifrex.match(line)
        if pmatch:
            print("Error:  Badly formed #if statement at line " + str(lineno) + " (ignored)")
            if ifblock != -1:
                ifstack.append(ifblock)

            if ifblock == 1 or ifblock == -1:
                ifblock = 0
            else:
                ifblock = 2
            continue

        pmatch = badelserex.match(line)
        if pmatch:
            print("Error:  Badly formed #else statement at line " + str(lineno) + " (ignored)")
            ifblock = 2
            continue

        # Ignore all lines that are not satisfied by a conditional
        if ifblock == 0 or ifblock == 2:
            continue

        # Now do definition replacement on what's left (if anything)
        for keyword in keys:
            line = keyrex[keyword].sub(defines[keyword], line)
                
        # Output the line
        print(line, file=ofile, end='')

    if ifblock != -1 or ifstack != []:
        print("Error:  input file ended with an unterminated #if block.")

    if ifile != sys.stdin:
        ifile.close()
    return

def printusage(progname):
    print('Usage: ' + progname + ' input_file [output_file] [-options]')
    print('   Options are:')
    print('      -help         Print this help text.')
    print('      -ccomm        Remove C comments in /* ... */ delimiters.')
    print('      -D<def>       Define word <def> and set its value to 1.')
    print('      -D<def>=<val> Define word <def> and set its value to <val>.')
    print('      -I<dir>       Add <dir> to search path for input files.')
    return

if __name__ == '__main__':

   # Parse command line for options and arguments
    options = []
    arguments = []
    for item in sys.argv[1:]:
        if item.find('-', 0) == 0:
            options.append(item)
        else:
            arguments.append(item)

    if len(arguments) > 0:
        inputfile = arguments[0]
        if len(arguments) > 1:
            outputfile = arguments[1]
        else:
            outputfile = []
    else:
        printusage(sys.argv[0])
        sys.exit(0)

    defines = {}
    keyrex = {}
    keys = []
    incdirs = []
    ccomm = False
    for item in options:
        result = item.split('=')
        if result[0] == '-help':
            printusage(sys.argv[0])
            sys.exit(0)
        elif result[0] == '-ccomm':
            ccomm = True
        elif result[0][0:2] == '-I':
            incdirs.append(result[0][2:])
        elif result[0][0:2] == '-D':
            keyword = result[0][2:]
            try:
                value = result[1]
            except:
                value = '1'
            defines[keyword] = value
            keyrex[keyword] = re.compile(keyword)
            keys.append(keyword)
        else:
            print('Bad option ' + item + ', options are -help, -ccomm, -D<def> -I<dir>\n')
            sys.exit(1)

    if outputfile:
        ofile = open(outputfile, 'w')
    else:
        ofile = sys.stdout

    if not ofile:
        print("Error:  Cannot open file " + output_file + " for writing.")
        sys.exit(1)

    runpp(keys, keyrex, defines, ccomm, incdirs, inputfile, ofile)
    if ofile != sys.stdout:
        ofile.close()
    sys.exit(0)
