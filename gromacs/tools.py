# Copyright (c) 2009 Oliver Beckstein <orbeckst@gmail.com>
# Released under the GNU Public License 3 (or higher, your choice)
# See the file COPYING for details.

"""
:mod:`gromacs.tools` -- Gromacs commands classes
================================================

A Gromacs command class acts as a factory function that produces an
instance of a gromacs command (:class:`gromacs.core.GromacsCommand`)
with initial default values.

By convention, a class has the capitalized name of the corresponding Gromacs
tool; dots are replaced by underscores to make it a valid python identifier.

The list of Gromacs tools to be loaded is configured in
:data:`gromacs.config.gmx_tool_groups`.

It is also possible to extend the basic commands and patch in additional
functionality. For example, the :class:`GromacsCommandMultiIndex` class makes a
command accept multiple index files and concatenates them on the fly; the
behaviour mimics Gromacs' "multi-file" input that has not yet been enabled for
all tools.

.. autoclass:: GromacsCommandMultiIndex
   :members: run, _fake_multi_ndx, __del__

Example
-------

In this example we create two instances of the :class:`gromacs.tools.Trjconv` command (which
runs the Gromacs ``trjconv`` command)::

  import gromacs.tools as tools

  trjconv = tools.Trjconv()
  trjconv_compact = tools.Trjconv(ur='compact', center=True, boxcenter='tric', pbc='mol',
                                  input=('protein','system'),
                                  doc="Returns a compact representation of the system centered on the protein")

The first one, ``trjconv``, behaves as the standard commandline tool but the
second one, ``trjconv_compact``, will by default create a compact
representation of the input data by taking into account the shape of the unit
cell. Of course, the same effect can be obtained by providing the corresponding
arguments to ``trjconv`` but by naming the more specific command differently
one can easily build up a library of small tools that will solve a specifi,
repeatedly encountered problem reliably. This is particularly helpful when doing
interactive work.

Gromacs tools
-------------
.. The docs for the tool classes are auto generated.

.. autoclass:: Mdrun
   :members:
.. autoclass:: GridMAT_MD
   :members:
"""

__docformat__ = "restructuredtext en"

import os.path
import tempfile

import config
from core import GromacsCommand, Command
import utilities

def _generate_sphinx_class_string(clsname):
    return ".. class:: %(clsname)s\n    :noindex:\n" % vars()

#: This dict holds all generated classes.
registry = {}

# Auto-generate classes such as:
# class g_dist(GromacsCommand):
#     command_name = 'g_dist'

for name in sorted(config.load_tools):
    # make names valid python identifiers and use convention that class names are capitalized
    clsname = name.replace('.','_').replace('-','_').capitalize()  
    cls = type(clsname, (GromacsCommand,), {'command_name':'{}_mpi'.format(name),
                                            '__doc__': "Gromacs tool %(name)r." % vars()})
    registry[clsname] = cls      # registry keeps track of all classes
    # dynamically build the module doc string
    __doc__ += _generate_sphinx_class_string(clsname)

# modify/fix classes as necessary
# Note: 
# - check if class was defined in first place
# - replace class
# - update local context AND registry as done below

class GromacsCommandMultiIndex(GromacsCommand):
        def __init__(self, **kwargs):
            """Initialize instance.

            1) Sets up the combined index file.
            2) Inititialize :class:`~gromacs.core.GromacsCommand` with the 
               new index file.
            
            See the documentation for :class:`gromacs.core.GromacsCommand` for details. 
            """
            kwargs = self._fake_multi_ndx(**kwargs)
            super(GromacsCommandMultiIndex, self).__init__(**kwargs)

        def run(self,*args,**kwargs):
            """Run the command; make a combined multi-index file if necessary."""
            kwargs = self._fake_multi_ndx(**kwargs)            
            return super(GromacsCommandMultiIndex, self).run(*args, **kwargs)

        def _fake_multi_ndx(self, **kwargs):
            """Combine multiple index file into a single one and return appropriate kwargs.

            Calling the method combines multiple index files into a a single
            temporary one so that Gromacs tools that do not (yet) support multi
            file input for index files can be used transparently as if they did.

            If a temporary index file is required then it is deleted once the
            object is destroyed.

            :Returns:
              The method returns the input keyword arguments with the necessary
              changes to use the temporary index files.

            :Keywords: 
               Only the listed keywords have meaning for the method:

               *n* : filename or list of filenames
                  possibly multiple index files; *n* is replaced by the name of 
                  the temporary index file.
               *s* : filename
                  structure file (tpr, pdb, ...) or ``None``; if a structure file is 
                  supplied then the Gromacs default index groups are automatically added
                  to the temporary indexs file.

            :Example: 
               Used in derived classes that replace the standard
               :meth:`run` (or :meth:`__init__`) methods with something like::

                  def run(self,*args,**kwargs):
                      kwargs = self._fake_multi_ndx(**kwargs)            
                      return super(G_mindist, self).run(*args, **kwargs)

            """
            ndx = kwargs.get('n')
            if not (ndx is None or type(ndx) is str):
                if len(ndx) > 1:
                    # g_mindist cannot deal with multiple ndx files (at least 4.0.5)
                    # so we combine them in a temporary file; it is unlinked in __del__.
                    # self.multi_ndx stores file name for __del__
                    fd, self.multi_ndx = tempfile.mkstemp(suffix='.ndx', prefix='multi_')
                    make_ndx = Make_ndx(f=kwargs.get('s'), n=ndx)
                    rc,out,err = make_ndx(o=self.multi_ndx, input=['q'],  # concatenate all index files
                                          stdout=False, stderr=False)
                    self.orig_ndx = ndx
                    kwargs['n'] = self.multi_ndx
            return kwargs

        def __del__(self):
            """Clean up temporary multi-index files if they were used."""
            # XXX: does not seem to work when closing the interpreter?!
            try:
                # self.multi_ndx <-- _fake_multi_index()
                utilities.unlink_gmx(self.multi_ndx)
            except (AttributeError, OSError):
                pass
            # XXX: type error --- can't use super in __del__?
            #super(GromacsCommandMultiIndex, self).__del__()

# patching up...

if 'G_mindist' in registry:
    # let G_mindist handle multiple ndx files
    class G_mindist(GromacsCommandMultiIndex):
        """Gromacs tool 'g_mindist' (with patch to handle multiple ndx files)."""
        command_name = 'g_mindist'
    registry['G_mindist'] = G_mindist

if 'G_dist' in registry:
    # let G_dist handle multiple ndx files
    class G_dist(GromacsCommandMultiIndex):
        """Gromacs tool 'g_dist' (with patch to handle multiple ndx files)."""
        command_name = 'g_dist'
    registry['G_dist'] = G_dist

# TODO: generate multi index classes via type(), not copy&paste as above...


# load additional scripts from config
for rec in config.load_scripts:
    name, clsname, doc = rec
    exec_name = os.path.basename(name)
    registry[clsname] = type(clsname, (Command,), 
                          {'command_name':name,
                           '__doc__': "External tool %(exec_name)r\n\n%(doc)s." % vars()})


# finally, add everything
globals().update(registry)        # add classes to module's scope
__all__ = registry.keys()

#  and clean up the module scope
cls = clsname = name = rec = doc = None  # make sure they exist, because the next line
del rec, name, cls, clsname, doc  # would throw NameError if no tool was configured

