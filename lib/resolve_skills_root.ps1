function Resolve-GraphifyySkillsRoot {
    param(
        [string]$SkillDirHint = $env:GRAPHIFYY_SKILL_DIR
    )
    if ($SkillDirHint) {
        $ipynb = Join-Path $SkillDirHint "ipynb_split.py"
        $lv = Join-Path $SkillDirHint "lvdash_split.py"
        if (Test-Path -LiteralPath $ipynb) {
            return (Split-Path $SkillDirHint -Parent)
        }
        if (Test-Path -LiteralPath $lv) {
            return (Split-Path $SkillDirHint -Parent)
        }
    }
    if ($PSScriptRoot) {
        $ipynbHere = Join-Path $PSScriptRoot "ipynb_split.py"
        $lvHere = Join-Path $PSScriptRoot "lvdash_split.py"
        if ((Test-Path -LiteralPath $ipynbHere) -or (Test-Path -LiteralPath $lvHere)) {
            return (Split-Path $PSScriptRoot -Parent)
        }
    }
    $cwd = (Get-Location).Path
    $userHome = if ($env:HOME) { $env:HOME } else { $env:USERPROFILE }
    $candidates = @()
    if ($env:GRAPHIFYY_SKILLS_ROOT) {
        $candidates += $env:GRAPHIFYY_SKILLS_ROOT
    }
    $candidates += @(
        $cwd,
        (Join-Path $cwd ".claude\skills\graphifyy-skills"),
        (Join-Path $userHome ".claude\skills\graphifyy-skills"),
        (Join-Path $cwd ".cursor\skills\graphifyy-skills")
    )
    foreach ($root in $candidates) {
        if (-not $root) { continue }
        $ipynb = Join-Path $root "ipynb-graphify\ipynb_split.py"
        $lv = Join-Path $root "databricks-graphify\lvdash_split.py"
        if ((Test-Path -LiteralPath $ipynb) -and (Test-Path -LiteralPath $lv)) {
            return (Resolve-Path -LiteralPath $root).Path
        }
    }
    throw "graphifyy-skills not found: install to ~/.claude/skills/graphifyy-skills or .claude/skills/graphifyy-skills (or set GRAPHIFYY_SKILLS_ROOT)."
}
