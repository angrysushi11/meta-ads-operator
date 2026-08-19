# Originating production workflow — not standalone validation

This is a bounded case report, not a universal Meta benchmark.

It describes the private implementation that informed this generalized
package. The public standalone distribution has not yet completed its own live
Meta smoke test. Its first external validation must be a separately authorized
one-ad PAUSED proof with exact readback, not a batch.

In one e-commerce batch, the operator created and individually
verified 17 new paused ads in 3 minutes 50 seconds, about 13.5 seconds per ad.
The earlier browser workflow averaged about 22 minutes per ad in this specific
process.

Spreadsheet-imported ads on this account hit Meta error `#3738001`. Fresh
API-created image, creative, and ad objects later succeeded. This does not
prove that the API bypasses account trust, policy, review, or delivery
restrictions, and `#3738001` should not be translated into a Meta explanation
that Meta itself did not provide.

The implementation reused and adapted the MIT-licensed KonQuest project; it
was not written entirely from scratch. The private hardened test suite
progressed from 185 to 188 to 189 passing tests.
