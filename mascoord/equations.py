class Linear:
    name = 'linear'

    def __init__(self, a, b, c):
        pass


class Quadratic:
    name = 'quadratic'

    def __init__(self, a, b, c):
        self.coefficients = {'a': a, 'b': b, 'c': c}

        self.formula = f'{a} * x^2 + {b} * x * y + {c} * y^2'
        self.ddx_formula = f'2 * {a} * x + {b} * y'
        self.ddy_formula = f'{b} * x + 2 * {c} * y'

    def calculate(self, x, y):
        a, b, c = self.coefficients['a'], self.coefficients['b'], self.coefficients['c']
        return a * x ** 2 + b * x * y + c * y ** 2

    def ddx(self, x, y):
        a, b = self.coefficients['a'], self.coefficients['b']
        return 2 * a * x + b * y

    def ddy(self, x, y):
        b, c = self.coefficients['b'], self.coefficients['c']
        return b * x + 2 * c * y

    def __str__(self):
        return self.formula
