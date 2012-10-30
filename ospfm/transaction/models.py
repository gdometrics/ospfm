#    Copyright 2012 Sebastien Maccagnoni-Munch
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

from sqlalchemy import Boolean, Column, Date, ForeignKey, func,\
                       Integer, Numeric, String
from sqlalchemy.orm import relationship, backref
from sqlalchemy.schema import UniqueConstraint

from ospfm.database import Base, session


class Account(Base):
    __tablename__ = 'account'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    currency_id = Column(ForeignKey('currency.id'))
    start_balance = Column(Numeric(15, 3), nullable=False)

    currency = relationship('Currency')
    account_owners = relationship('AccountOwner', cascade='all, delete-orphan')
    transactions_account = relationship('TransactionAccount',
                                        cascade='all, delete-orphan')

    def balance(self):
        balance = session.query(
            func.sum(TransactionAccount.amount)
        ).filter(
            TransactionAccount.account_id == self.id
        ).one()[0]
        if balance:
            return self.start_balance + balance
        else:
            return self.start_balance


    def as_dict(self, short=False):
        if short:
            return {
                'id': self.id,
                'name': self.name,
                'currency': self.currency.isocode
            }
        else:
            return {
                'id': self.id,
                'name': self.name,
                'currency': self.currency.isocode,
                'start_balance': self.start_balance,
                'balance': self.balance()
            }


class AccountOwner(Base):
    __tablename__ = 'accountowner'
    account_id = Column(ForeignKey('account.id'), primary_key=True)
    owner_username = Column(ForeignKey('user.username'), primary_key=True)

    account = relationship('Account')
    owner = relationship('User')


class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True)
    owner_username = Column(ForeignKey('user.username'), nullable=False)
    parent_id = Column(ForeignKey('category.id'))
    currency_id = Column(ForeignKey('currency.id'))
    name = Column(String(50), nullable=False)

    owner = relationship('User')
    children = relationship('Category',
                            backref=backref('parent', remote_side=[id]),
                            order_by='Category.name')
    currency = relationship('Currency')

    # When deleting a category, delete all its associations to transactions
    transactions_category = relationship('TransactionCategory',
                                         cascade='all, delete-orphan')

    # TODO: Category balance for some periods
    #def balance(self):

    def as_dict(self, parent=True, children=True):
        desc = {
            'id': self.id,
            'name': self.name,
            'currency': self.currency.isocode
        }
        if parent and self.parent_id:
            desc['parent'] = self.parent_id
        if children and self.children:
            desc['children'] = [c.as_dict(False) for c in self.children]
        return desc

    def contains_category(self, categoryid):
        if self.id == categoryid:
            return True
        if self.children:
            for c in self.children:
                if c.contains_category(categoryid):
                    return True
        return False


class Transaction(Base):
    __tablename__ = 'transaction'
    id = Column(Integer, primary_key=True)
    owner_username = Column(ForeignKey('user.username'), nullable=False)
    description = Column(String(200), nullable=False)
    original_description = Column(String(200), nullable=False)
    amount = Column(Numeric(15, 3), nullable=False)
    currency_id = Column(ForeignKey('currency.id'), nullable=False)
    date = Column(Date, nullable=False)

    owner = relationship('User')
    currency = relationship('Currency')

    transaction_accounts = relationship('TransactionAccount',
                                        cascade='all, delete-orphan')
    transaction_categories = relationship('TransactionCategory',
                                          cascade='all, delete-orphan')

    def as_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'original_description': self.original_description,
            'amount': self.amount,
            'currency': self.currency.isocode,
            'date': self.date.strftime('%Y-%m-%d'),
            'accounts': [ta.as_dict() for ta in self.transaction_accounts],
            'categories': [tc.as_dict() for tc in self.transaction_categories]
        }


class TransactionAccount(Base):
    __tablename__ = 'transactionaccount'
    transaction_id = Column(ForeignKey('transaction.id'), primary_key=True)
    account_id = Column(ForeignKey('account.id'), primary_key=True)
    amount = Column(Numeric(15, 3), nullable=False)
    verified = Column(Boolean, nullable=False, default=False)

    transaction = relationship('Transaction')
    account = relationship('Account')

    def as_dict(self):
        data = self.account.as_dict(short=True)
        data['amount'] = self.amount
        data['verified'] = self.verified
        return data

    def as_tuple(self):
        return (self.account_id, self.amount)


class TransactionCategory(Base):
    __tablename__ = 'transactioncategory'
    transaction_id = Column(ForeignKey('transaction.id'), primary_key=True)
    category_id = Column(ForeignKey('category.id'), primary_key=True)
    amount = Column(Numeric(15, 3), nullable=False)

    transaction = relationship('Transaction')
    category = relationship('Category')

    def as_dict(self):
        data = self.category.as_dict(parent=False,children=False)
        data['amount'] = self.amount
        return data

    def as_tuple(self):
        return (self.category_id, self.amount)
