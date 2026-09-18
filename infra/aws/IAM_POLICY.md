# IAM Policy — GitHub Actions Deploy Role

This is the exact IAM policy this project uses for the OIDC-federated deploy
role (task 4.3; FR-26, SEC-03, SEC-04). It's already implemented as
CloudFormation in `infra/aws/oidc-github-actions.yaml`, and
**running that template (`infra/aws/README.md`, Step 2) is still the
recommended path** — it creates everything below in one command, correctly,
every time. This file exists for two reasons: to answer *"trust policy vs.
permissions policy — together or separate?"* precisely, and to walk through
the manual AWS Console steps in case you want to build it by hand, inspect
it before running the template, or just see exactly where each piece of
JSON lives.

## Quick answer: they are always separate — this isn't a choice

An IAM role has exactly **one trust policy** and, separately, **one or more
permissions policies**. IAM does not let you merge them into a single JSON
document or paste them into the same box — they live in different places on
the role, no matter which tool creates the role:

| | Trust policy | Permissions policy |
|---|---|---|
| **What it answers** | *Who* is allowed to assume this role? | *What* can the role do once assumed? |
| **In the console** | Role → **Trust relationships** tab | Role → **Permissions** tab |
| **How many** | Exactly one, always (every role has exactly one, even if it's never edited) | Zero or more (you can attach several) |
| **CLI/API name** | `AssumeRolePolicyDocument` | An attached/inline `PolicyDocument` |
| **In this project's CloudFormation** | `GitHubActionsDeployRole.Properties.AssumeRolePolicyDocument` | `GitHubActionsDeployRole.Properties.Policies[0].PolicyDocument` (named `JuiceShopEC2Deploy`) |

So: **two separate JSON documents, pasted into two separate console
screens.** The steps below tell you exactly which one goes where.

---

## Manual creation walkthrough (AWS Console)

Skip this whole section if you're running the CloudFormation template — it
does all of this for you. Use this only if you're building the role by hand.

### Step 1 — Create the OIDC identity provider (one-time per account)

This is a separate object from the role; the role's trust policy will
reference it. Skip this step entirely if your account already has a GitHub
Actions OIDC provider from another project (then use
`CreateOidcProvider=false` in the CFN template, or just point the trust
policy at the existing provider's ARN).

1. AWS Console → **IAM** → left sidebar → **Identity providers** → **Add provider**.
2. Provider type: **OpenID Connect**.
3. Provider URL: `https://token.actions.githubusercontent.com` → click **Get thumbprint**.
4. Audience: `sts.amazonaws.com`.
5. **Add provider**.
6. Open the provider you just created and copy its **ARN** — you'll need it in Step 3. It looks like:
   `arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com`

### Step 2 — Start creating the role

1. IAM → **Roles** → **Create role**.
2. Trusted entity type: **Web identity**.
3. Identity provider: select the one from Step 1 (`token.actions.githubusercontent.com`).
4. Audience: `sts.amazonaws.com`.
5. If the console offers optional GitHub organization/repository fields here, you can fill them in, but **don't rely on them alone** — you'll overwrite the trust policy with the exact condition from this doc in Step 4 anyway, so it's safe to leave them blank.
6. **Next**.
7. On the **Add permissions** page: select nothing and click **Next**. (This page only offers pre-existing *managed* policies; our permissions policy is custom and *inline*, which you'll add in Step 5, after the role exists.)
8. Role name: `github-actions-devsecops-deploy` (must match this exactly if you want `infra/aws/README.md`'s existing instructions and this project's other docs to line up).
9. **Create role**.

### Step 3 — Confirm the OIDC provider's ARN

Open **IAM → Identity providers → token.actions.githubusercontent.com** and copy the ARN shown there (same value as Step 1.6). You'll paste it into the trust policy next.

### Step 4 — Add the trust policy

*This is where the first JSON block below goes — nowhere else.*

1. Open your new role: **IAM → Roles → github-actions-devsecops-deploy**.
2. Click the **Trust relationships** tab.
3. Click **Edit trust policy**.
4. **Delete everything in the editor** and paste the full JSON from
   [§1 below](#1-trust-policy--who-can-assume-this-role), with
   `<ACCOUNT_ID>` replaced by your real 12-digit AWS account id (find it top-right of the console, under your account name, or via `aws sts get-caller-identity`).
5. **Update policy**.

### Step 5 — Add the permissions policy

*This is where the second JSON block below goes — a completely separate screen from Step 4.*

1. Same role page → click the **Permissions** tab.
2. **Add permissions** → **Create inline policy**.
3. Click the **JSON** tab (top-right of the policy editor) to switch out of the visual builder.
4. Paste the full JSON from
   [§2 below](#2-permissions-policy--what-the-role-can-do), with
   `<REGION>` and `<ACCOUNT_ID>` replaced by your deploy region (e.g. `us-east-1`) and account id.
5. **Next**.
6. Policy name: `JuiceShopEC2Deploy` (matches the CFN template's naming, so this project's other docs stay consistent).
7. **Create policy**.

### Step 6 — Get the role ARN

Role page → top of the **Summary** panel → copy the **ARN**. It looks like:
`arn:aws:iam::<ACCOUNT_ID>:role/github-actions-devsecops-deploy`

This is the value you set as the `AWS_ASSUME_ROLE_ARN` **repository
variable** in GitHub (Settings → Secrets and variables → Actions →
Variables — see `infra/aws/README.md` Step 3). It is not a secret; it's
just an identifier, so a repository *variable* is correct, not a *secret*.

### Step 7 — Verify

Run the `AWS OIDC Federation Test (task 4.3)` workflow
(`.github/workflows/aws-oidc-test.yml`) from the Actions tab
(**Run workflow**). Its `Print the assumed identity` step should print an
ARN ending in `role/github-actions-devsecops-deploy` with no
`AccessDenied`. That's the same acceptance check the CloudFormation path uses.

---

## 1. Trust policy — who can assume this role

Only GitHub Actions workflow runs from this exact repo, on `main`, may
assume the role — federated via OIDC, no IAM user, no access keys.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:King-Wealth247/Automated-DevSecOps-Security-Gate:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

Replace `<ACCOUNT_ID>` with your AWS account id (the CFN template fills this
in for you automatically via `!GetAtt`/`!Ref`, since the OIDC provider ARN
is a stack output).

- **`aud` (audience)** must equal `sts.amazonaws.com` — this is what GitHub
  puts in the token, and it's fixed, not configurable.
- **`sub` (subject)**, matched with `StringLike` so `AllowedRef` can carry a
  wildcard (e.g. `refs/tags/*`) if you ever widen it, is scoped to
  `repo:King-Wealth247/Automated-DevSecOps-Security-Gate:ref:refs/heads/main`
  — no other repo, fork, branch, or PR can assume this role.
- **Hardening planned at task 4.5** (once the real deploy step lands): add
  `"token.actions.githubusercontent.com:workflow": "ci.yml"` under
  `StringEquals`, so no *other* workflow file in this same repo could assume
  the role either — deferred for now so the standalone OIDC probe workflow
  (`aws-oidc-test.yml`) can still use it to validate federation.

---

## 2. Permissions policy — what the role can do

Named `JuiceShopEC2Deploy` in the template. Every write action is scoped to
exactly one tagged EC2 instance; nothing else in the account is reachable.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DiscoverTestInstance",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceStatus",
        "ec2:DescribeTags"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IssueDeployCommandToTestInstance",
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand"
      ],
      "Resource": [
        "arn:aws:ec2:<REGION>:<ACCOUNT_ID>:instance/*"
      ],
      "Condition": {
        "StringEquals": {
          "ssm:ResourceTag/DevSecOps": "juice-shop"
        }
      }
    },
    {
      "Sid": "UseAwsRunShellDocument",
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand"
      ],
      "Resource": [
        "arn:aws:ssm:<REGION>::document/AWS-RunShellScript"
      ]
    },
    {
      "Sid": "ObserveDeployCommand",
      "Effect": "Allow",
      "Action": [
        "ssm:CancelCommand",
        "ssm:GetCommandInvocation",
        "ssm:ListCommandInvocations",
        "ssm:ListCommands"
      ],
      "Resource": "*"
    }
  ]
}
```

Replace `<REGION>`/`<ACCOUNT_ID>` with your deploy region and account id
(the CFN template fills these in automatically via `${AWS::Region}` /
`${AWS::AccountId}`).

### Why each statement exists

| Sid | Grants | Why |
|---|---|---|
| `DiscoverTestInstance` | Read-only `ec2:Describe*` | Lets the deploy step *find* the test instance by its tag before issuing a command. AWS's `Describe*` actions don't support resource-level scoping, so `Resource: "*"` is the AWS-mandated minimum here — it's read-only, so this can't be used to touch anything. |
| `IssueDeployCommandToTestInstance` | `ssm:SendCommand`, scoped to `ec2:*:*:instance/*` **and** `Condition: ssm:ResourceTag/DevSecOps=juice-shop` | This is the only *write* path the role has. The tag condition means it literally cannot target any instance except the one tagged `DevSecOps=juice-shop` — an untagged instance, or a differently-tagged one, is unreachable by this role, full stop. |
| `UseAwsRunShellDocument` | `ssm:SendCommand` on the `AWS-RunShellScript` document ARN only | `SendCommand` needs a separate grant on the *document* it runs, and AWS-managed documents can't be tagged, so this can't be folded into the tag-conditioned statement above. Scoped to exactly one document — not `ssm:document/*`. |
| `ObserveDeployCommand` | `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:ListCommands`, `ssm:CancelCommand` | Lets the deploy step poll for success/failure and cancel a hung command. AWS provides no command-ARN to scope these against, so `Resource: "*"` is again the mandated minimum — but these are status/cancel actions on commands *this role itself issued*, not a path to new access. |

### What this role explicitly **cannot** do

- No `iam:*` — it cannot create, modify, or escalate any IAM entity, including itself.
- No `ec2:RunInstances`, `ec2:TerminateInstances`, or any other EC2 write action — it can only *observe* instances and *command* the one pre-tagged one via SSM.
- No `s3:*`, no `rds:*`, no access to any other AWS service at all.
- No action against any instance lacking the exact tag `DevSecOps=juice-shop`.
- No long-lived credentials anywhere — every session is federated per-run via OIDC and expires (`MaxSessionDuration: 3600`, i.e. 1 hour).

---

## Recommended: let CloudFormation do all of the above in one step

```powershell
aws cloudformation deploy `
  --template-file infra/aws/oidc-github-actions.yaml `
  --stack-name devsecops-github-oidc `
  --capabilities CAPABILITY_NAMED_IAM `
  --parameter-overrides `
    GitHubOrg=King-Wealth247 `
    GitHubRepo=Automated-DevSecOps-Security-Gate `
    AllowedRef=refs/heads/main `
    InstanceTagKey=DevSecOps `
    InstanceTagValue=juice-shop
```

This single command creates the OIDC provider (Step 1), the role (Step 2),
the trust policy (Step 4), and the permissions policy (Step 5) together,
with no placeholder substitution needed — CloudFormation fills in
`<ACCOUNT_ID>`/`<REGION>` itself. The manual walkthrough above exists so you
can see exactly what this command is doing, not as a better alternative to it.
