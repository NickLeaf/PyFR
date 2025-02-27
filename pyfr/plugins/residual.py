# -*- coding: utf-8 -*-

import numpy as np

from pyfr.mpiutil import get_comm_rank_root, mpi
from pyfr.plugins.base import BasePlugin, init_csv


class ResidualPlugin(BasePlugin):
    name = 'residual'
    systems = ['*']
    formulations = ['std']

    def __init__(self, intg, cfgsect, suffix):
        super().__init__(intg, cfgsect, suffix)

        comm, rank, root = get_comm_rank_root()

        # Output frequency
        self.nsteps = self.cfg.getint(cfgsect, 'nsteps')

        # The root rank needs to open the output file
        if rank == root:
            header = ['t'] + intg.system.elementscls.convarmap[self.ndims]

            # Open
            self.outf = init_csv(self.cfg, cfgsect, ','.join(header))

        # Prep work if an output is due next step
        self._prep_next_output(intg)

    def _prep_next_output(self, intg):
        if (intg.nacptsteps + 1) % self.nsteps == 0:
            self._prev = [s.copy() for s in intg.soln]
            self._tprev = intg.tcurr

    def __call__(self, intg):
        # If an output is due this step
        if intg.nacptsteps % self.nsteps == 0 and intg.nacptsteps:
            # MPI info
            comm, rank, root = get_comm_rank_root()

            # Previous and current solution
            prev = self._prev
            curr = intg.soln

            # Square of the residual vector for each variable
            resid = sum(np.linalg.norm(p - c, axis=(0, 2))**2
                        for p, c in zip(prev, curr))

            # Reduce and, if we are the root rank, output
            if rank != root:
                comm.Reduce(resid, None, op=mpi.SUM, root=root)
            else:
                comm.Reduce(mpi.IN_PLACE, resid, op=mpi.SUM, root=root)

                # Normalise
                resid = np.sqrt(resid) / (intg.tcurr - self._tprev)

                # Write
                print(intg.tcurr, *resid, sep=',', file=self.outf)

                # Flush to disk
                self.outf.flush()

            del self._prev, self._tprev

        # Prep work if an output is due next step
        self._prep_next_output(intg)

