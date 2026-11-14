"""M-owned real WISE acceptance: simultaneous two-source native photometry.
Historical I blended-stack evidence is preserved under validation/G4b-wise-stacks.
"""
import asyncio
from argparse import Namespace
from m_acceptance import main
if __name__ == '__main__':
    asyncio.run(main(Namespace(target='wise0855',product='spectrum')))
