#!/bin/sh
python src/xnode_admin/tests/mock_studio_tests.py ./mock_studio_message_v2.json &
python src/xnode_admin/main.py --remote http://localhost:5000/xnodes/functions --uuid I5KMFECV11H-VX5K78G4P7I --access-token Tah6WlMnal0mpka6ki8jHmoD9hhK9KXc81xyNjvSt1hm1nj74dlM4W8jPEdPdmSJD1JVba+eDHEceUysRZnplw== ./
