#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) 2020-2023, Bodo Schulz <bodo@boone-schulz.de>
# Apache-2.0 (see LICENSE or https://opensource.org/license/apache-2-0)
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function
import json
import difflib
import itertools
import textwrap
import typing


class SideBySide:
    """
      -> https://gist.github.com/jlumbroso/3ef433b4402b4f157728920a66cc15ed
    """

    def __init__(self, module, left, right):
        """
          Initialize all needed Variables
        """
        self.module = module

        if isinstance(left, dict):
            left = json.dumps(left, indent=2)

        if isinstance(right, dict):
            right = json.dumps(right, indent=2)

        if isinstance(left, str):
            left = left.split("\n")

        if isinstance(right, str):
            right = right.split("\n")

        self.default_separator = " | "

        self.left = left
        self.right = right
        self.width = 140
        self.as_string = True
        self.left_title = "  Original"
        self.right_title = "  Update"

    def side_by_side(self,
                     left: typing.List[str],
                     right: typing.List[str],
                     width: int = 78,
                     as_string: bool = False,
                     separator: typing.Optional[str] = None,
                     left_title: typing.Optional[str] = None,
                     right_title: typing.Optional[str] = None,
                     ) -> typing.Union[str, typing.List[str]]:
        """
            Returns either the list of lines, or string of lines, that results from
            merging the two lists side-by-side.

            :param left: Lines of text to place on the left side
            :type left: typing.List[str]
            :param right: Lines of text to place on the right side
            :type right: typing.List[str]
            :param width: Character width of the overall output, defaults to 78
            :type width: int, optional
            :param as_string: Whether to return a string (as opposed to a list of strings), defaults to False
            :type as_string: bool, optional
            :param separator: String separating the left and right side, defaults to " | "
            :type separator: typing.Optional[str], optional
            :param left_title: Title to place on the left side, defaults to None
            :type left_title: typing.Optional[str], optional
            :param right_title: Title to place on the right side, defaults to None
            :type right_title: typing.Optional[str], optional
            :return: Lines or text of the merged side-by-side output.
            :rtype: typing.Union[str, typing.List[str]]
        """
        separator = separator or self.default_separator

        mid_width = (width - len(separator) - (1 - width % 2)) // 2

        tw = textwrap.TextWrapper(
            width=mid_width,
            break_long_words=False,
            replace_whitespace=False
        )

        def reflow(lines):
            wrapped_lines = list(map(tw.wrap, lines))
            wrapped_lines_with_linebreaks = [
                [""] if len(wls) == 0 else wls
                for wls in wrapped_lines
            ]
            return list(itertools.chain.from_iterable(wrapped_lines_with_linebreaks))

        left = reflow(left)
        right = reflow(right)

        zip_pairs = itertools.zip_longest(left, right)

        if left_title is not None or right_title is not None:
            left_title = left_title or ""
            right_title = right_title or ""
            zip_pairs = [
                (left_title, right_title),
                (mid_width * "-", mid_width * "-")
            ] + list(zip_pairs)

        lines = []
        for left, right in zip_pairs:
            left = left or ""
            right = right or ""
            spaces = (" " * max(0, mid_width - len(left)))

            line = f"{left}{spaces}{separator}{right}"
            lines.append(line)

        if as_string:
            return "\n".join(lines)

        return lines

    def better_diff(self,
                    left: typing.List[str],
                    right: typing.List[str],
                    width: int = 78,
                    as_string: bool = True,
                    separator: typing.Optional[str] = None,
                    left_title: typing.Optional[str] = None,
                    right_title: typing.Optional[str] = None,
                    ) -> typing.Union[str, typing.List[str]]:
        """
            Returns a side-by-side comparison of the two provided inputs, showing
            common lines between both inputs, and the lines that are unique to each.

            :param left: Lines of text to place on the left side
            :type left: typing.List[str]
            :param right: Lines of text to place on the right side
            :type right: typing.List[str]
            :param width: Character width of the overall output, defaults to 78
            :type width: int, optional
            :param as_string: Whether to return a string (as opposed to a list of strings), defaults to True
            :type as_string: bool, optional
            :param separator: String separating the left and right side, defaults to " | "
            :type separator: typing.Optional[str], optional
            :param left_title: Title to place on the left side, defaults to None
            :type left_title: typing.Optional[str], optional
            :param right_title: Title to place on the right side, defaults to None
            :type right_title: typing.Optional[str], optional
            :return: Lines or text of the merged side-by-side diff comparison output.
            :rtype: typing.Union[str, typing.List[str]]
        """
        differ = difflib.Differ()

        left_side = []
        right_side = []

        if isinstance(left, str):
            left = left.split("\n")

        if isinstance(right, str):
            right = right.split("\n")

        # adapted from
        # LINK: https://stackoverflow.com/a/66091742/408734
        difflines = list(differ.compare(left, right))

        for line in difflines:
            """
            """
            op = line[0]
            tail = line[2:]

            if op == " ":
                # line is same in both
                left_side.append(f" {tail}")
                right_side.append(f" {tail}")

            elif op == "-":
                # line is only on the left
                left_side.append(f" {tail}")
                right_side.append("-")

            elif op == "+":
                # line is only on the right
                left_side.append("+")
                right_side.append(f" {tail}")

        return self.side_by_side(
            left=left_side,
            right=right_side,
            width=width,
            as_string=as_string,
            separator=separator,
            left_title=left_title,
            right_title=right_title,
        )

    def diff(self,
             width: int = 78,
             as_string: bool = True,
             separator: typing.Optional[str] = None,
             left_title: typing.Optional[str] = None,
             right_title: typing.Optional[str] = None,
             ) -> typing.Union[str, typing.List[str]]:
        """
        """
        return self.better_diff(self.left, self.right, width, as_string, separator, left_title, right_title)
