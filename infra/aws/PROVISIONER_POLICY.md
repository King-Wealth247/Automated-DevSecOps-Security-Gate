# Provisioner Bootstrap Policy — for the human AWS user, not GitHub Actions

**This is a different policy for a different identity than `IAM_POLICY.md`.**
`IAM_POLICY.md` documents the role GitHub Actions assumes at CI time
(federated, no long-lived keys, scoped to one EC2 instance). This file is
for the **local AWS user you personally run `aws cloudformation deploy`
as** (e.g. `King_Wealth_01`) — the one-time, disposable credential that
creates that role in the first place. It needs a different, broader set of
permissions than the role it's creating, because it has to be able to
create IAM/CloudFormation resources at all.

If you hit:

```
AccessDenied ... User: arn:aws:iam::<ACCOUNT_ID>:user/King_Wealth_01 is not
authorized to perform: cloudformation:DescribeStacks on resource ...
```

this is why: that user currently has no CloudFormation or IAM rights at all.
This policy grants exactly what `aws cloudformation deploy` needs to create
`infra/aws/oidc-github-actions.yaml`'s stack — nothing more.

## Why not just attach `AdministratorAccess`?

You can — it's simpler, and since this credential is meant to be deleted or
detached right after provisioning succeeds (see `infra/aws/README.md`), a
brief admin grant is a reasonable shortcut for a personal/course sandbox
account. This file is the scoped alternative, for when you'd rather not
grant admin even temporarily.

## Steps

1. AWS Console → **IAM → Users → King_Wealth_01** (or whichever user runs the deploy) → **Permissions** tab.
2. **Add permissions → Create inline policy**.
3. Click the **JSON** tab (top-right of the editor).
4. Paste the policy below, replacing `<ACCOUNT_ID>` (your 12-digit account id — top-right of the console, or `aws sts get-caller-identity`) and `<REGION>` (your deploy region, e.g. `us-east-1` — or `aws configure get region`).
5. **Next** → name it `DevSecOpsOidcStackProvisioner` → **Create policy**.
6. Re-run the `aws cloudformation deploy` command from `infra/aws/README.md`.
7. **Once the stack succeeds and the probe workflow passes**, remove this policy from the user (Permissions tab → this policy → **Remove**) — it has no further purpose once the stack exists; the actual CI/CD access from then on goes through the separate, tightly-scoped `github-actions-devsecops-deploy` role, not this user.

## The policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationStackLifecycle",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ListChangeSets"
      ],
      "Resource": "arn:aws:cloudformation:<REGION>:<ACCOUNT_ID>:stack/devsecops-github-oidc/*"
    },
    {
      "Sid": "CloudFormationTemplateValidation",
      "Effect": "Allow",
      "Action": [
        "cloudformation:GetTemplateSummary",
        "cloudformation:ValidateTemplate"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CreateOrUpdateOidcProvider",
      "Effect": "Allow",
      "Action": [
        "iam:CreateOpenIDConnectProvider",
        "iam:GetOpenIDConnectProvider",
        "iam:TagOpenIDConnectProvider",
        "iam:UntagOpenIDConnectProvider",
        "iam:UpdateOpenIDConnectProviderThumbprint",
        "iam:DeleteOpenIDConnectProvider"
      ],
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
    },
    {
      "Sid": "CreateOrUpdateDeployRole",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:UpdateRole",
        "iam:UpdateRoleDescription",
        "iam:UpdateAssumeRolePolicy",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:DeleteRole"
      ],
      "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/github-actions-devsecops-deploy"
    }
  ]
}
```

### Why each statement exists

| Sid | Covers | Why scoped this way |
|---|---|---|
| `CloudFormationStackLifecycle` | Create/update/delete the stack, plus every action `aws cloudformation deploy` actually calls under the hood (it always goes through a change set, never `CreateStack`/`UpdateStack` directly — those two are included anyway for console use or future scripted calls) | Resource is scoped to `stack/devsecops-github-oidc/*` — the exact stack name this project uses. CloudFormation supports resource-level permissions on the stack-name pattern even for the create action itself (the unique-ID suffix is wildcarded), so this user cannot touch any *other* stack in the account. |
| `CloudFormationTemplateValidation` | `GetTemplateSummary` (called by `deploy` to validate `--parameter-overrides` against the template's declared `Parameters`), `ValidateTemplate` | Neither action operates on an existing stack resource (they inspect a template body directly), so CloudFormation doesn't support resource-level scoping for them — `Resource: "*"` is the AWS-mandated minimum, and both are read-only/inspection actions. |
| `CreateOrUpdateOidcProvider` | Every lifecycle action on the GitHub Actions OIDC provider | Scoped to the one provider URL this template creates (`token.actions.githubusercontent.com`) — cannot create or modify any other identity provider. Includes delete/update so a `cloudformation deploy` re-run or eventual stack deletion doesn't need a second permissions grant. |
| `CreateOrUpdateDeployRole` | Every lifecycle action on the role, *including* its inline policy (`PutRolePolicy`/`GetRolePolicy`/`DeleteRolePolicy` — an inline policy isn't its own IAM resource, so it's authorized via the role's ARN) | Scoped to the exact role name `github-actions-devsecops-deploy` — this user cannot create, modify, or delete any *other* IAM role, and specifically cannot grant itself or anything else broader access. |

### What this policy explicitly does **not** grant

- No access to any other CloudFormation stack in the account.
- No `iam:CreateUser`, `iam:CreateAccessKey`, `iam:AttachUserPolicy`, or any
  action that could create or widen a *different* identity's access —
  including this user's own.
- No EC2, SSM, S3, or any other service access — this user only provisions
  the OIDC role; it never needs to touch the EC2 test instance itself.
- No wildcard IAM resource (`role/*`, `oidc-provider/*`) — every grant names
  the one specific resource this stack creates.
