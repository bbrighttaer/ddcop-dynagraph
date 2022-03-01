import py_expression_eval
import collections

parser = py_expression_eval.Parser()


class Equation:
    name = 'Equation'

    # raw equation structure
    formula = ''

    # formula of first order differential w.r.t. x
    ddx_formula = ''

    # formula of first order differential w.r.t. y
    ddy_formula = ''

    def __init__(self, **kwargs):
        self.coefficients = kwargs
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
    formula = 'a * x^2 + b * x * y + c * y^2'
    ddx_formula = '2 * a * x + b * y'
    ddy_formula = 'b * x + 2 * c * y'

    def __init__(self, a, b, c):
        super(Linear, self).__init__(a=a, b=b, c=c)


class Quadratic(Equation):
    name = 'quadratic'
    formula = ''
    ddx_formula = ''
    ddy_formula = ''


class Cubic(Equation):
    name = 'cubic'
    formula = ''
    ddx_formula = ''
    ddy_formula = ''


equations_directory = {
    Linear.name: Linear,
    Quadratic.name: Quadratic,
    Cubic.name: Cubic
}
equations_directory = collections.defaultdict(lambda: Linear, equations_directory)
