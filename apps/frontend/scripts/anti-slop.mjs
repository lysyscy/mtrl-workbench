const assertions = new Set(['TSAsExpression', 'TSTypeAssertion']);

export default {
  meta: { name: 'anti-slop' },
  rules: {
    'no-double-assertion': {
      create(context) {
        function check(node) {
          if (assertions.has(node.expression.type)) {
            context.report({ node, message: 'Validate the value or construct the target type directly.' });
          }
        }
        return { TSAsExpression: check, TSTypeAssertion: check };
      },
    },
    'no-empty-catch': {
      create(context) {
        return {
          CatchClause(node) {
            if (node.body.body.length === 0) context.report({ node, message: 'Handle the caught error.' });
          },
        };
      },
    },
    'no-lint-exemption': {
      create(context) {
        return {
          Program() {
            for (const comment of context.sourceCode.getAllComments()) {
              if (/^\s*(?:(?:eslint|oxlint)(?:\b|-(?:disable|enable)\b)|@ts-(?:ignore|expect-error)\b)/u.test(comment.value)) {
                context.report({ loc: comment.loc, message: 'Fix the lint finding in the source.' });
              }
            }
          },
        };
      },
    },
  },
};
