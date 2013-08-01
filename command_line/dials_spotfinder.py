#!/usr/bin/env python
#
# dials.dials_spotfinder.py
#
#  Copyright (C) 2013 Diamond Light Source
#
#  Author: James Parkhurst
#
#  This code is distributed under the BSD license, a copy of which is
#  included in the root directory of this package.
from __future__ import division
from dials.util.script import ScriptRunner
# LIBTBX_SET_DISPATCHER_NAME dials.spotfinder
# LIBTBX_PRE_DISPATCHER_INCLUDE_SH export PHENIX_GUI_ENVIRONMENT=1
# LIBTBX_PRE_DISPATCHER_INCLUDE_SH export BOOST_ADAPTBX_FPE_DEFAULT=1

class Script(ScriptRunner):
    '''A class for running the script.'''

    def __init__(self):
        '''Initialise the script.'''

        # The script usage
        usage = "usage: %prog [options] [param.phil] sweep.json"

        # Initialise the base class
        ScriptRunner.__init__(self, usage=usage)

        # Output filename option
        self.config().add_option(
            '-o', '--output-filename',
            dest = 'output_filename',
            type = 'string', default = 'spots.pickle',
            help = 'Set the filename for found spots.')

    def main(self, params, options, args):
        '''Execute the script.'''
        from dials.algorithms.peak_finding.spotfinder_factory import SpotFinderFactory
        from dials.algorithms import shoebox
        from dials.model.serialize import load, dump
        from dials.util.command_line import Command

        # Check the number of arguments is correct
        if len(args) != 1:
            self.config().print_help()
            return

        # Get the integrator from the input parameters
        print 'Configurating spot finder from input parameters'
        find_spots = SpotFinderFactory.from_parameters(params)

        # Try to load the models
        print 'Loading initial models from {0}'.format(args[0])
        sweep = load.sweep(args[0])
        if len(sweep) == 1:
            raise RuntimeError("spotfinding currently requires "
                               "more than one image.")

        # Find the strong spots in the sweep
        print 'Finding strong spots'
        reflections = find_spots(sweep)

        # View the spots if you like
        if params.spotfinder.image_viewer:
            from dials.util.spotfinder_wrap import spot_wrapper
            spot_wrapper(working_phil=params).display(
                sweep_filenames=sweep.paths(),
                reflections=reflections)

        # Save the reflections to file
        Command.start('Saving {0} reflections to {1}'.format(
            len(reflections), options.output_filename))
        dump.reflections(reflections, options.output_filename)
        Command.end('Saved {0} reflections to {1}'.format(
            len(reflections), options.output_filename))


if __name__ == '__main__':
    script = Script()
    script.run()
