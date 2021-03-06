#    Copyright 2012-2013 Sebastien Maccagnoni-Munch
#
#    This file is part of OSPFM.
#
#    OSPFM is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    OSPFM is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with OSPFM.  If not, see <http://www.gnu.org/licenses/>.

from decimal import Decimal

from ospfm import db, helpers
from ospfm.core import models as core
from ospfm.core import currency as corecurrency
from ospfm.transaction import models
from ospfm.objects import Object


class Account(Object):

    def __own_account(self, accountid):
        return models.Account.query.options(
                        db.joinedload(models.Account.currency)
                ).join(models.AccountOwner).filter(
                    db.and_(
                        models.AccountOwner.owner_username == self.username,
                        models.Account.id == accountid
                    )
                ).first()

    def list(self):
        accounts = models.Account.query.options(
                        db.joinedload(models.Account.currency)
        ).join(models.AccountOwner).filter(
            models.AccountOwner.owner_username == self.username
        ).all()
        # Calculate the total balance, in the user's preferred currency
        totalbalance = 0
        totalcurrency = core.User.query.options(
                            db.joinedload(core.User.preferred_currency)
                        ).get(self.username).preferred_currency
        for account in accounts:
            totalbalance += account.balance(self.username)[0] * \
            helpers.rate(self.username,
                         account.currency.isocode,
                         totalcurrency.isocode)
        return {
            'accounts': [a.as_dict(self.username) for a in accounts],
            'total': {
                'balance': totalbalance,
                'currency': totalcurrency.isocode
            }
        }

    def create(self):
        if not (
            'currency' in self.args and
            'name' in self.args and
            'start_balance' in self.args
        ):
            self.badrequest(
                 "Please provide the account name, currency and start balance")
        currency = core.Currency.query.filter(
            db.and_(
                core.Currency.isocode == self.args['currency'],
                db.or_(
                    core.Currency.owner_username == self.username,
                    core.Currency.owner_username == None
                )
            )
        ).first()
        if not currency:
            self.badrequest("This currency does not exist")

        name = self.args['name']
        start_balance = self.args['start_balance']

        a = models.Account(
                name=name,
                currency=currency,
                start_balance=start_balance
        )
        ao = models.AccountOwner(account=a, owner_username=self.username)
        db.session.add_all((a, ao))
        db.session.commit()
        self.add_to_response('totalbalance')
        return a.as_dict(self.username)

    def read(self, accountid):
        account = self.__own_account(accountid)
        if account:
            return account.as_dict(self.username)
        self.notfound('This account does not exist or you do not own it')

    def update(self, accountid):
        account = self.__own_account(accountid)
        if not account:
            self.notfound(
               'Nonexistent account cannot be modified (or you do not own it)')
        if 'name' in self.args:
            account.name = self.args['name']
        if 'currency' in self.args:
            # Do not update currency if account has transactions
            if not models.TransactionAccount.query.filter(
                        models.TransactionAccount.account == account
                   ).count():
                currency = core.Currency.query.filter(
                    db.and_(
                        core.Currency.isocode == self.args['currency'],
                        db.or_(
                            core.Currency.owner_username == self.username,
                            core.Currency.owner_username == None
                        )
                    )
                ).first()
                if currency:
                    account.currency = currency
        if 'start_balance' in self.args:
            account.start_balance = Decimal(self.args['start_balance'])
            self.add_to_response('totalbalance')
        db.session.commit()
        return account.as_dict(self.username)

    def delete(self, accountid):
        account = self.__own_account(accountid)
        if not account:
            self.notfound(
                'Nonexistent account cannot be deleted (or you do not own it)')
        db.session.delete(account)
        db.session.commit()
        self.add_to_response('totalbalance')
