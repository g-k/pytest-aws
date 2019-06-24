import json
import tempfile

from foxsec_tools import utils as s3_utils


class GitHubException(Exception):
    pass


class GitHubFileNotFoundException(GitHubException):
    # error downloading file
    pass


def get_data_file(
    organization,
    date,
    method_name,
    call_args,
    call_kwargs,
    cache=None,
    result_from_error=None,
    debug_calls=False,
    debug_cache=False,
):
    """
    Fetches and return final data

    TODO: get caching working
    """
    if debug_calls:
        print("calling", method_name, "on", organization)

    result = None
    if cache is not None:
        ckey = cache_key(organization, method_name)
        result = cache.get(ckey, None)

        if debug_cache and result is not None:
            print("found cached value for", ckey)

    if result is None:
        # import pudb; pudb.set_trace()
        # build expected URL
        srcloc = "foxsec-metrics"
        srcname = f"github/object_json/{date}-{organization}.db.obj.json"
        locfile = tempfile.NamedTemporaryFile()
        try:
            s3_utils.download_file(locfile.name, "s3", srcloc, srcname)
            with open(locfile.name) as f:
                result = f.read()
        except Exception as e:
            raise GitHubFileNotFoundException(str(e))

        if cache is not None:
            if debug_cache:
                print("setting cache value for", ckey)

            cache.set(ckey, result)

    return result


def get_heroku_resource(
    organization,
    method_name,
    call_args,
    call_kwargs,
    cache=None,
    result_from_error=None,
    debug_calls=False,
    debug_cache=False,
):
    """
    Fetches and return final data

    TODO: more refactoring of herokuadmintools needed, so can:
        - cache all members
        - cache all apps of member
    """
    if debug_calls:
        print("calling", method_name, "on", organization)

    result = None
    if cache is not None:
        ckey = cache_key(organization, method_name)
        result = cache.get(ckey, None)

        if debug_cache and result is not None:
            print("found cached value for", ckey)

    if result is None:
        # convert from defaultdict with values as sets
        # each user is a dict as described here:
        #  https://devcenter.heroku.com/articles/platform-api-reference#team-member
        # import pudb; pudb.set_trace()
        users = list(get_users(organization))
        ##role_users = {k: list(v) for k, v in
        ##        find_users_missing_2fa(organization).items()}
        ## App data collection takes forever -- don't get unless needed
        ##apps = {k: list(v) for k, v in
        ##        find_affected_apps(users, organization).items()}
        result = [
            {
                # HerokuDataSets.ROLE_USER: users,
                # HerokuDataSets.APP_USER: apps,
                HerokuDataSets.USER: users
            }
        ]

        if cache is not None:
            if debug_cache:
                print("setting cache value for", ckey)

            cache.set(ckey, result)

    return result


class HerokuDataSets:
    # We use an IntEnum so keys can be ordered, which is done deep in some
    # libraries when we use the enums as dict keys
    ROLE_USER = 1  # tuple of (role, user)
    APP_USER = 2  # tuple of (app, user)
    USER = 2  # list of dicts with JSON response fields


class HerokuAdminClient:

    # ensure we have access from instance
    data_set_names = HerokuDataSets

    def __init__(self, organization, cache, debug_calls, debug_cache, offline):
        self.organization = organization
        self.cache = cache

        self.debug_calls = debug_calls
        self.debug_cache = debug_cache
        self.offline = offline

        self.results = []

    def get(
        self,
        method_name,
        call_args,
        call_kwargs,
        result_from_error=None,
        do_not_cache=False,
    ):

        if self.offline:
            self.results = []
        else:
            self.results = list(
                get_heroku_resource(
                    self.organization,
                    method_name,
                    call_args,
                    call_kwargs,
                    cache=self.cache if not do_not_cache else None,
                    result_from_error=result_from_error,
                    debug_calls=self.debug_calls,
                    debug_cache=self.debug_cache,
                )
            )

        return self

    def find_users_missing_2fa(self):
        return self.extract_key(HerokuDataSets.ROLE_USER, {})

    def find_affected_apps(self):
        return self.extract_key(HerokuDataSets.APP_USER, {})

    def values(self):
        """Returns the wrapped value

        >>> c = HerokuAdminClient([None], None, None, None, offline=True)
        >>> c.results = []
        >>> c.values()
        []
        """
        return self.results

    def extract_key(self, key, default=None):
        """
        From an iterable of dicts returns the value with the given
        keys discarding other values:

        >>> c = HerokuAdminClient([None], None, None, None, offline=True)
        >>> c.results = [{'id': 1}, {'id': 2}]
        >>> c.extract_key('id').results
        [1, 2]

        When the key does not exist it returns the second arg which defaults to None:

        >>> c = HerokuAdminClient([None], None, None, None, offline=True)
        >>> c.results = [{'id': 1}, {}]
        >>> c.extract_key('id').results
        [1, None]

        But not to primitives:

        >>> c.results = [{'PolicyNames': ['P1', 'P2']}]
        >>> c.extract_key('PolicyNames').results
        [['P1', 'P2']]
        """
        tmp = []
        for result in self.results:
            keyed_result = default

            if key in result:
                keyed_result = result[key]

            tmp.append(keyed_result)

        self.results = tmp
        return self

    def debug(self):
        print(self.results)
        return self