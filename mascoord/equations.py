import py_expression_eval
import collections

parser = py_expression_eval.Parser()


class Equation:
    name = 'Equation'

    def __init__(self, **kwargs):
        self._eq = None
        self._ddy = None
        self._ddx = None

        self.coefficients = kwargs
        # raw equation structure
        self.formula = ''

        # formula of first order differential w.r.t. x
        self.ddx_formula = ''

        # formula of first order differential w.r.t. y
        self.ddy_formula = ''

    def set_equation_and_differentials(self):
        self._eq = self._parse(self.formula)
        self._ddx = self._parse(self.ddx_formula)
        self._ddy = self._parse(self.ddy_formula)

    @property
    def equation(self):
        return self._eq

    @property
    def ddx(self):
        return self._ddx

    @property
    def ddy(self):
        return self._ddy

    def _parse(self, formula):
        eq = parser.parse(formula)
        for key in self.coefficients:
            eq = eq.substitute(key, self.coefficients[key])
        return eq

    def __str__(self):
        return f'{self.equation.toString()}, ddx={self.ddx.toString()}, ddy={self.ddy.toString()}'


class Linear(Equation):
    name = 'linear'

    def __init__(self, a, b, c):
        super(Linear, self).__init__(a=a, b=b, c=c)


class Quadratic(Equation):
    name = 'quadratic'

    def __init__(self, a, b, c):
        super(Quadratic, self).__init__(a=a, b=b, c=c)

        self.formula = 'a * x^2 + b * x * y + c * y^2'
        self.ddx_formula = '2 * a * x + b * y'
        self.ddy_formula = 'b * x + 2 * c * y'

        self.set_equation_and_differentials()


class Cubic(Equation):
    name = 'cubic'


equations_directory = {
    Linear.name: Linear,
    Quadratic.name: Quadratic,
    Cubic.name: Cubic
}
equations_directory = collections.defaultdict(lambda: Linear, equations_directory)
