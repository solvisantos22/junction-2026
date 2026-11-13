"""Scripted controls for interpreting controller evaluation results."""

from .api import PublicTools


def do_nothing(tools: PublicTools):
    """Issue no commands; the evaluator still consumes the full horizon."""
    return None
