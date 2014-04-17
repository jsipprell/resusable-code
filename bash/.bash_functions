#!/bin/bash
# easy to use find <dir> -name <globspec>
shopt -s extglob

function gitlog() {
  git log --show-signature \
          --format=short \
          --abbrev-commit \
          --simplify-merges \
          --graph \
          "$@"
}

function __ffind() {
  set -f
  local dir="$1"; shift
  local spec="$1"; shift
  local before_spec="$1"; shift
  local -a after_spec=("$@")

  #echo "before_spec = '$before_spec'"
  set -- $before_spec

  #echo "find \"$dir\" "$@" -name \"$spec\" ${after_spec[*]}"
  find "$dir" "$@" -name "$spec" "${after_spec[@]}"
}

function _ffind() {
  set -f
  local dir='.'
  local spec='*'
  local type='f'
  local -a non_args=()

  while [[ $# -gt 0 ]] && [[ $1 = -* ]]; do
    [[ $1 = '-type' ]] && [[ $# -gt 1 ]] && {
      type="$2"; shift; echo "type set to $type"; true
    } || before_args+=("$1")
    shift
  done
  
  while [[ $# -gt 0 ]] && [[ $1 != -* ]]; do
    non_args+=("$1")
    shift
  done

  [[ $# -gt 0 ]] && args+=("$@")
  [[ $type != '-' ]] && before_args+=('-type' "$type")
  set -- "${non_args[@]}"

  [[ $# -ge 2 ]] && { dir="$1"; shift; }
  [[ $# -ge 1 ]] && { spec="$1"; shift; }
  [[ $# -gt 0 ]] && args+=("$@")

  __ffind "$dir" "$spec" "${before_args[*]}" "${args[@]}"
}

# bash locals are actually dynamically scoped, not lexically, so $args
# is visible by anything ffind*() calls.
function ffind() {
  local -a before_args=('-not' '-path' '*/.svn/*')
  local -a args=()
  _ffind "$@"
}

function ffind0() {
  local -a before_args=()
  local -a args=('-print0')
  _ffind "$@"
}

function is_git() {
  local d=$(pwd)
  local -i rv=1

  [[ $1 ]] && { cd "$1" || return $?; }
  git status >/dev/null 2>&1 && let rv=0
  [[ $1 ]] && { cd "$pwd" || let rv+=$?; }
  return $rv
}

function is_svn() {
  local d=$(pwd)
  local -i rv=1

  [[ $1 ]] && { cd "$1" || return $?; }
  svn info >/dev/null 2>&1 && let rv=0
  [[ $1 ]] && { cd "$pwd" || let rv+=$?; }
  return $rv
}

function pythonlib() {
  local set_pythonpath=
  local pythonpath=~/lib/python

  if [ $# -gt 0 ]; then
    case $(tr 'A-Z' 'a-z' <<<"$1") in
      1|true|yes|local)
        set_pythonpath=yes
        cus
        ;;
      0|false|no|system)
        set_pythonpath=no
        ;;
      *)
        set_pythonpath=yes
        pythonpath="$1"
        ;;
    esac
  fi

  if [ -z "$set_pythonpath" ]; then
    if [ -z "$PYTHONPATH" ]; then
      set_pythonpath=yes
    else
      set_pythonpath=no
    fi
  fi

  case "$set_pythonpath" in
    yes)
      export PYTHONPATH=$(echo $pythonpath)
      echo "Using user python path ($PYTHONPATH)"
      ;;
    no)
      unset PYTHONPATH
      echo "Using system python path."
      ;;
  esac
}

function merge() {
  local revs=

  while [ $# -gt 0 ]; do
    revs="$revs$1"
    shift
  done
  
  if [ -z "$revs" ]; then
    echo "usage: merge svn-revisions"
    return 1
  fi
  
  svn up && svnmerge merge -b "-r$revs" &&
    test -e svnmerge-commit-message.txt && svn commit -F svnmerge-commit-message.txt
}

function gcfpush() {
  local -i rc=0
  pushd ~/src/config || return $?
  git push origin master; let rc=$?
  [[ $rc -eq 0 ]] && { git push origin; let rc=$?; }
  [[ $rc -eq 0 ]] && [[ $# -gt 0 ]] && { git push origin "$@"; let rc=$?; }
  popd
  return $rc
}

function gmergeone() {
  local src=
  local branch=
  local curbranch=
  local -i rc=0

  [[ $# -gt 0 ]] && {
    branch=$(tr a-z A-Z <<<"$1")
    shift
  }

  while [[ $# -gt 0 ]]; do
    src="$src${src:+ }$1"
    shift
  done

  [[ $src ]] || src=master

  if [[ -z "$branch" ]]; then
    echo "usage: mergeone LAB|DEVEL|TEST|PROD <optional-git-source-branch>" >&2
    return 1
  fi

  curbranch=$(git branch --list --no-color --no-column | awk '{if($1=="*") print $2}')
  if [[ $curbranch != $branch ]]; then
    git checkout "$branch" || return $?
    git rebase -p || return $?
  else
    curbranch=
  fi

  git merge --ff-only "$src"; let rc=$?

  [[ $curbranch ]] && git checkout "$curbranch"
  return $rc
}

function mergeone() {
  local revs=
  local branch=
  local -i rc=0

  [ $# -gt 0 ] && {
    branch=$(tr a-z A-Z <<<"$1")
    shift
  }
  
  while [ $# -gt 0 ]; do
    revs="$revs$1"
    shift
  done

  if [ -z $"$revs" -o -z $"$branch" ]; then 
    echo "usage: mergeone LAB|TEST|PROD svn-revisions"
    return 1
  fi

  #trap 'set +e' RETURN
  pushd ~/src/config-$branch || return 1
    merge "$revs"; rc=$?
  popd
  
  return $rc
}

function gmergedev() {
  local d=$(pwd)
  local -i rc=0
  cd ~/src/config || return $?
  gmergeone devel "$@"
  let rc=$?
  cd "$d"
  return $rc
}

alias gmergedevel=gmergedev
alias mergedevel=gmergedev
alias ggrep='git grep -e'

function gmergelab() {
  local d=$(pwd)
  local -i rc=0
  cd ~/src/config || return $?
  gmergeone devel "$@"; let rc=$?
  [[ $rc -eq 0 ]] && { gmergeone lab "$@"; let rc=$?; }
  cd "$d"
  return $rc
}

function mergelab() {
  if ! is_svn; then
    local -i rc=0
    gmergelab "$@"
    let rc=$?
    [[ $rc -eq 0 ]] && { gcfpush; let rc=$?; }
    return $rc
  fi
  mergeone lab "$@"
  return $?
}

function gmergetest() {
  local d=$(pwd)
  local -i rc=0
  cd ~/src/config || return $?
  gmergeone devel "$@"; let rc=$?
  [[ $rc -eq 0 ]] && { gmergeone lab "$@"; let rc=$?; }
  [[ $rc -eq 0 ]] && { gmergeone test "$@"; let rc=$?; }
  cd "$d"
  return $rc
}

function mergetest() {
  if ! is_svn; then
    local -i rc=0
    gmergetest "$@"
    let rc=$?
    [[ $rc -eq 0 ]] && { gcfpush; let rc=$?; }
    return $rc
  fi
  mergeone lab || return $?
  mergeone test
  return $?
}

function gmergeprod() {
  local d=$(pwd)
  local -i rc=0
  cd ~/src/config || return $?
  gmergeone prod "$@"
  let rc=$?
  cd "$d"
  return $rc
}

function mergeprod() {
  if ! is_svn; then
    local -i rc=0
    gmergeprod "$@"
    let rc=$?
    [[ $rc -eq 0 ]] && { gcfpush; let rc=$?; }
    return $rc
  fi
  mergeone prod "$@"
  return $?
}

function gmergeall() {
  local -i rc=0
  pushd ~/src
    pushd config; let rc=$?
    if [[ $rc -eq 0 ]]; then
      gmergetest "$@"; let rc=$?
      [[ $rc -eq 0 ]] && { gmergeprod "$@"; let rc=$?; }
      popd
    fi
  popd
  return $rc
}

function mergeall() {
  local revs=
  local -i rc=0
  if ! is_svn; then
    gmergeall
    let rc=$?
    [[ $rc -eq 0 ]] && { gcfpush; let rc=$?; }
    return $rc
  fi
  while [ $# -gt 0 ]; do
    revs="$revs$1"
    shift
  done
  
  if [ -z "$revs" ]; then
    echo "usage: mergeall svn-revisions"
    return 1
  fi
  
 #trap 'set +e' RETURN

  pushd ~/src
    pushd config-TEST
      merge "$revs"; rc=$?
    popd
    
    [ $rc -eq 0 ] && {
      pushd config-LAB
        merge "$revs"; rc=$?
      popd
    }
    [ $rc -eq 0 ] && {
      pushd config-PROD
        merge "$revs"; rc=$?
      popd
    }
  popd
  
  return $rc
}

function gitfind() {
  local color='--color=auto'
  local grep='git grep'
  local -a switches=()
  local -a args=()
  local -i count=0
  local ref=

  tty -s && color='--color=always'
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --color|--color=*)
        switches+=("$1")
        color=
        ;;
      -i)
        switches+=('-i')
        ;;
      +*)
        ref="${1#+}"
        ;;
      --)
        if [[ ${#args[@]} -gt 0 ]]; then
          switches+=("${args[@]}")
          args=()
        fi
        args+=('--')
        shift
        args+=("$@")
        set -- ''
        ;;
      -*)
        switches+=("$1")
        let count++
        ;;
      *)
        if [[ $count -eq 0 ]] && [[ ${#args[@]} -eq 0 ]] && [[ "${1/[^a-zA-Z]*/}" = "$1" ]]; then
          args+=('(?<=^|[^a-zA-Z])'"${1}"'(?=[^a-zA-Z]|$)')
        else
          args+=("$1")
        fi
        ;;
    esac
    shift
  done

  [[ $color ]] && switches=("$color" "${switches[@]}")
  if [[ ${args[0]} != '--' ]] && [[ ${#args[@]} -ge 2 ]]; then
    switches+=("${args[0]}")
    if [[ $ref ]]; then
      switches+=("$ref")
    fi
    args[0]='--'
  elif [[ $ref ]]; then
    switches+=("$ref")
  fi
  $grep "${switches[@]}" "${args[@]}"
}

function extfind() {
  local color='--color=auto'
  local grep=fgrep
  local custom_grep=
  local -a args=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --color|--color=*)
        args+=("$1")
        color=
        ;;
      --*)
        [[ $1 != '--' ]] && args+=("$1") ||:
        shift
        [[ $# -gt 0 ]] && args+=("$@") ||:
        set -- ''
        ;;
      -*)
        [[ $custom_grep ]] && args+=("$1") || { grep="${1#-}"; custom_grep=yes; }
        ;;
      *)
        args+=("$1")
        ;;
    esac
    shift
  done

  tty -s && color='--color=always'

  [[ ${#args[*]} -lt 2 ]] && {
    echo "fail: extfind .py ${grep}-args"
    return 1
  }

  local ext="*.${args[0]##*.}"; unset args[0]
  find . -name "$ext" -print0 | xargs -0 "$grep" $color "${args[@]}"
}

function ppfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.pp'
  else
    extfind pp "$@"
  fi
}

function rbfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.rb'
  else
    extfind rb "$@"
  fi
}

function pyfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.py'
  else
    extfind py "$@"
  fi
}

function plfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.pl'
  else
    extfind pl "$@"
  fi
}

function erbfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.erb'
  else
    extfind erb "$@"
  fi
}

function xmlfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.xml' '*.xslt'
  else
    extfind xml "$@"
  fi
}

function yamlfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.yaml' '*.yml'
  else
    extfind yaml "$@"
  fi
}

function ymlfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.yaml' '*.yml'
  else
    extfind yml "$@"
  fi
}

function htmlfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.html'
  else
    extfind html "$@"
  fi
}

function propfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.properties'
  else
    extfind properties "$@"
  fi
}

alias propertiesfind=propfind

function cfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.c' '*.h' '*.cpp' '*.m'
  else
    extfind c "$@"
  fi
}

function conffind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.conf' '*.conf.erb'
  else
    extfind conf "$@"
  fi
}

function vclfind() {
  if git status >/dev/null 2>&1; then
    gitfind "$@" -- '*.vcl' '*.vcl.erb'
  else
    extfind conf "$@"
  fi
}

function xgrep() {
  local filespec=''
  local grepargs=''
  local pattern=''
  local color='--color=auto'
  tty -s && color='--color=always' ||:

  while [ $# -gt 0 ]; do
    case "$1" in
      --color*)
        grepargs="$grepargs${grepargs:+ }$1"
        color=""
        ;;
      -*)
        grepargs="$grepargs${grepargs:+ }$1"
        ;;
      *)
        if [ -z "$filespec" ]; then
          filespec="$1"
        else
          pattern="$pattern${pattern:+\\ }$1"
        fi
        ;;
    esac
    shift
  done
  
  if [ -z "$filespec" -o -z "$pattern" ]; then
    echo "usage: xgrep [grep-options] filespec pattern"
    return 1
  fi
  
  grepargs="$color${color:+ }$grepargs"
  find . -name "$filespec" -print0 | xargs -0 fgrep $grepargs "$pattern"
}

join() {
  local -a input
  local sep=','
  local resep='/'

  [[ $1 = -* ]] && {
    case "$1" in
      -c|--comma)
        sep=','
        ;;
      -s|--sep|--separator)
        shift
        sep="$1"
        ;;
      -s*)
        sep=${1#-s}
        ;;
      --separator=*)
        sep=${1#--separator}
        ;;
      --sep=*)
        sep=${1#--sep}
        ;;
      *)
        echo 'usage: join [-s|--separator=CHAR] [elements ...]'
        echo '  Joins "elements" with CHAR (default is ",")'
        return 1
        ;;
    esac
    shift
  }

  sep=$(echo "$sep" | sed -E -e 's/%/%%/g')
  
  [ "$resep" = "$sep" ] && resep='_'
  [ "$resep" = "$sep" ] && resep='@'

  printf "$sep%s" "$@" | sed -e "s$resep^$sep$resep$resep"
}

is_member() {
  # return 0 if first arg is present in remaining args
  # if first arg is -p or --print, output the argument
  # if the first arg is -- it is ignored, removed and the second
  # and subsequent args are treated literally; this is a way
  # to seach for '-p' or '--print' literally.

  local reset_extglob=
  local print=
  local output=
  local needle
  local a
  local -i notfound=1
  local -i found=0
  local -i rc=$notfound

  shopt -q extglob || reset_extglob='shopt -u extglob'
  shopt -s extglob

  while [[ $1 == -* ]]; do
    case "$1" in
      -p|--print|--print=*)
        print="${1#--print=}"
        ;;
      -v)
        notfound=0
        found=1
        rc=$notfound
        ;;
      --)
        shift
        break
        ;;
      -*)
        echo "is_member: invalid option '$1'."
        return 10
        ;;
    esac
    shift
  done

  case "$print" in
    \>\&*)
      output="$print"
      ;;
    stderr)
      output='>&2'
      ;;
    stdout)
      output='>&1'
      ;;
  esac

  needle="$1"; shift
  for a; do
    if [ "$needle" = "$a" ]; then
      [[ $found -eq 0 ]] && [[ $print ]] && eval echo "$a" $output
      let rc=found
      break
    fi
  done
  
  [[ $found -eq 1 ]] && [[ $rc -eq $notfound ]] && eval echo "$needle" $output
  $reset_extglob
  return $rc
}

is_not_member() {
  # Inverse of is_member, same thing as calling: is_member -v ...
  is_member -v "$@"
}

# vi: :set sts=2 sw=2 ai et tw=0:
