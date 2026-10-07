import unittest

from routingpy.direction import Direction


class DirectionTest(unittest.TestCase):
    def test_km(self):
        more_than_one = Direction(distance=8577)
        exactly_one = Direction(distance=1000)
        less_than_one = Direction(distance=123)

        self.assertEqual(more_than_one.km, 8.577)
        self.assertEqual(exactly_one.km, 1)
        self.assertEqual(less_than_one.km, 0.123)

    def test_mi(self):
        more_than_one = Direction(distance=3200)
        exactly_one = Direction(distance=1609.344)
        less_than_one = Direction(distance=835)

        self.assertAlmostEqual(more_than_one.mi, 1.9883878)
        self.assertAlmostEqual(exactly_one.mi, 1)
        self.assertAlmostEqual(less_than_one.mi, 0.51884492)
