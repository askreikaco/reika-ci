// reika-ci stylelint preset for the CSS ratchet gate (scripts/css-ratchet.mjs).
// Legacy code may already break these rules; the gate fails only when a count rises.
// Exception format (reason is required):
//   /* stylelint-disable-next-line declaration-no-important -- imp: <reason> */
module.exports = {
  rules: {
    'declaration-no-important': true,
    'selector-max-id': 0,
    // conv 39 disallowed selectors (ratchet: count may not rise)
    'selector-disallowed-list': [
      '/^html\\s+body/',
      '/:root.*body/',
      '/#z_/',
      '/\\.brxe-[a-z0-9]{6}\\b/',
      '/\\.brx-/',
      '/body\\.page-id-/',
      '/\\.postid-/',
      // REIKA CONDITIONAL SELECTORS (css-authoring §I.13, owner 2026-11-27): :is() around :not() or an ID
      '/:is\\([^)]*:not\\(/',
      '/:is\\([^)]*#/',
    ],
    // REIKA §I.13 (owner 2026-11-27): no :not()/:has(), no attribute substring operators
    'selector-pseudo-class-disallowed-list': ['not', 'has'],
    'selector-attribute-operator-disallowed-list': ['*=', '^=', '$='],
    'selector-max-specificity': '0,3,0',
    'no-duplicate-selectors': true,
  },
  reportDescriptionlessDisables: true,
};
